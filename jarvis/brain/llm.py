"""Le "cerveau" : Claude avec appel d'outils (tool use)."""
from __future__ import annotations

import logging

import anthropic

from jarvis.brain.tools import ConfirmFn, ToolRegistry
from jarvis.config import DEFAULTS

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

SYSTEM_PROMPT = """\
Tu es {name}, l'assistant vocal personnel qui tourne sur le PC de l'utilisateur, \
dans l'esprit de J.A.R.V.I.S. dans Iron Man.

Contexte : nous sommes {jour} {quantieme} {mois} {annee}, il est {heure}.

Règles :
- Réponds toujours en français, en 1 à 3 phrases courtes : ta réponse est lue à voix haute. \
Pas de markdown, pas de liste, pas d'émojis, pas d'URL.
- Ton : poli, calme, efficace, avec une pointe d'humour pince-sans-rire.{title_rule}
- Pour agir sur le PC ou obtenir une information (météo, heure...), utilise les outils. \
N'invente jamais le résultat d'un outil ; si un outil échoue, dis-le simplement.
- Sans lieu précisé, la ville par défaut pour la météo est {default_city}.
- Après une action, confirme brièvement ("C'est fait.", "J'ouvre YouTube.").
- La demande vient d'une transcription vocale qui peut contenir des erreurs : \
interprète avec bon sens. Si c'est vraiment ambigu, pose UNE courte question.
- Pour les questions de culture générale, réponds de mémoire et précise si l'information \
peut avoir changé récemment.
- Si on te demande une action que tes outils ne permettent pas, explique-le poliment.
"""


class Brain:
    def __init__(self, config: dict, registry: ToolRegistry,
                 confirm: ConfirmFn | None = None, client=None) -> None:
        llm_cfg = {**DEFAULTS["llm"], **config.get("llm", {})}
        self.config = config
        self.registry = registry
        self.confirm = confirm
        self.model = llm_cfg["model"]
        self.max_tokens = llm_cfg["max_tokens"]
        self.max_messages = llm_cfg["history_turns"] * 2
        self.client = client or anthropic.Anthropic()  # lit ANTHROPIC_API_KEY
        self.history: list[dict] = []

    def _system(self) -> str:
        import datetime as dt

        now = dt.datetime.now()
        a = self.config["assistant"]
        title = a.get("user_title") or ""
        return SYSTEM_PROMPT.format(
            name=a["name"],
            jour=JOURS[now.weekday()],
            quantieme=now.day,
            mois=MOIS[now.month - 1],
            annee=now.year,
            heure=now.strftime("%H:%M"),
            default_city=a["default_city"],
            title_rule=f' Tu t\'adresses à l\'utilisateur par "{title}".' if title else "",
        )

    def respond(self, user_text: str) -> str:
        """Traite une demande, exécute les outils nécessaires, renvoie la réponse parlée."""
        self.history.append({"role": "user", "content": user_text})
        messages = list(self.history)
        system = self._system()
        tools = self.registry.schemas()

        try:
            response = None
            for _ in range(MAX_TOOL_ROUNDS):
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system,
                    tools=tools,
                    messages=messages,
                )
                messages.append({"role": "assistant", "content": response.content})
                if response.stop_reason != "tool_use":
                    break

                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        output = self.registry.execute(block.name, block.input, self.confirm)
                        results.append(
                            {"type": "tool_result", "tool_use_id": block.id, "content": output}
                        )
                messages.append({"role": "user", "content": results})
        except anthropic.APIError as exc:
            log.error("Erreur API Anthropic : %s", exc)
            self.history.pop()  # on oublie la demande qui a échoué
            return "Désolé, je n'arrive pas à joindre mon cerveau en ligne. Vérifiez la connexion et la clé API."

        text = ""
        if response is not None:
            text = "".join(b.text for b in response.content if b.type == "text").strip()
        text = text or "C'est fait."

        # On ne garde que le texte échangé (pas les blocs d'outils) pour un historique compact.
        self.history.append({"role": "assistant", "content": text})
        self.history = self.history[-self.max_messages:]
        return text
