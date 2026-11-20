"""Le "cerveau" : un modèle local servi par Ollama (gratuit, sans clé, hors ligne).

Ordre de traitement d'une demande :
  1. chemin rapide par règles (router.py) pour les commandes simples ;
  2. sinon, le modèle avec appel d'outils (tool calling).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re

import requests

from jarvis.brain.router import FastRouter
from jarvis.brain.tools import ConfirmFn, ToolRegistry
from jarvis.config import DEFAULTS

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

SYSTEM_PROMPT = """\
Tu es {name}, l'assistant vocal personnel qui tourne sur le PC de l'utilisateur, \
dans l'esprit de J.A.R.V.I.S. dans Iron Man.
Nous sommes {jour} {quantieme} {mois} {annee}, il est {heure}.

Règles :
- Réponds toujours en français, en 1 à 3 phrases courtes : ta réponse est lue à voix haute. \
Pas de markdown, pas de liste, pas d'émojis, pas d'URL.
- Ton poli, calme et efficace, avec une pointe d'humour.{title_rule}
- N'utilise un outil QUE si la demande exige une action sur le PC ou une information en direct \
(météo, heure). Pour une simple question de culture ou une conversation, réponds directement.
- N'invente jamais le résultat d'un outil. Si un outil échoue, dis-le simplement.
- Sans lieu précisé, la ville par défaut pour la météo est {default_city}.
- Après une action, confirme en quelques mots ("C'est fait.", "J'ouvre YouTube.").
- La demande vient d'une transcription vocale qui peut contenir des erreurs : interprète avec bon sens.
- Tu ne connais pas l'actualité récente : dis-le si on te la demande.
"""

THINK_RE = re.compile(r"<think>.*?</think>", re.S)


class OllamaError(RuntimeError):
    pass


class Brain:
    def __init__(self, config: dict, registry: ToolRegistry,
                 confirm: ConfirmFn | None = None) -> None:
        llm = {**DEFAULTS["llm"], **config.get("llm", {})}
        self.config = config
        self.registry = registry
        self.confirm = confirm
        self.base_url = llm["base_url"].rstrip("/")
        self.model = llm["model"]
        self.options = {"temperature": llm["temperature"], "num_ctx": llm["num_ctx"]}
        self.think = llm["think"]
        self.keep_alive = llm["keep_alive"]
        self.timeout = llm["timeout"]
        self.max_messages = llm["history_turns"] * 2
        self.router = FastRouter(config, registry, confirm) if llm["fast_path"] else None
        self.history: list[dict] = []

    # ------------------------------------------------------------ Ollama (HTTP)
    def check(self) -> str | None:
        """Vérifie qu'Ollama tourne et que le modèle est installé. Retourne un message d'erreur ou None."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
        except requests.RequestException:
            return ("Ollama ne répond pas. Installez-le (https://ollama.com/download), lancez-le, "
                    f"puis réessayez. Adresse testée : {self.base_url}")
        names = {m.get("name", "") for m in r.json().get("models", [])}
        wanted = self.model if ":" in self.model else self.model + ":latest"
        if wanted not in names and self.model not in names:
            return f"Le modèle '{self.model}' n'est pas installé. Lancez : ollama pull {self.model}"
        return None

    def warm_up(self) -> None:
        """Charge le modèle en VRAM à l'avance pour éviter 5-10 s d'attente à la 1re demande."""
        try:
            requests.post(f"{self.base_url}/api/generate",
                          json={"model": self.model, "prompt": "", "keep_alive": self.keep_alive},
                          timeout=self.timeout)
        except requests.RequestException:
            log.debug("Préchauffage du modèle impossible", exc_info=True)

    def _chat(self, messages: list[dict]) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": [{"type": "function",
                       "function": {"name": t["name"], "description": t["description"],
                                    "parameters": t["input_schema"]}}
                      for t in self.registry.schemas()],
            "stream": False,
            "options": self.options,
            "keep_alive": self.keep_alive,
        }
        if self.think is not None:
            payload["think"] = self.think
        r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        if r.status_code == 400 and "think" in r.text.lower() and "think" in payload:
            payload.pop("think")  # ce modèle ne gère pas le paramètre : on réessaie sans
            r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        if r.status_code != 200:
            raise OllamaError(f"Ollama a répondu {r.status_code} : {r.text[:200]}")
        return r.json()["message"]

    # ----------------------------------------------------------------- logique
    def _system(self) -> str:
        now = dt.datetime.now()
        a = self.config["assistant"]
        title = a.get("user_title") or ""
        return SYSTEM_PROMPT.format(
            name=a["name"], jour=JOURS[now.weekday()], quantieme=now.day,
            mois=MOIS[now.month - 1], annee=now.year, heure=now.strftime("%H:%M"),
            default_city=a["default_city"],
            title_rule=f' Tu t\'adresses à l\'utilisateur par "{title}".' if title else "",
        )

    def _remember(self, user_text: str, reply: str) -> None:
        self.history += [{"role": "user", "content": user_text},
                         {"role": "assistant", "content": reply}]
        self.history = self.history[-self.max_messages:]

    def respond(self, user_text: str) -> str:
        # 1) chemin rapide
        if self.router is not None:
            try:
                reply = self.router.route(user_text)
            except Exception:
                log.exception("Erreur du chemin rapide, bascule sur le modèle")
                reply = None
            if reply is not None:
                self._remember(user_text, reply)
                return reply

        # 2) modèle avec outils
        messages = [{"role": "system", "content": self._system()}, *self.history,
                    {"role": "user", "content": user_text}]
        content = ""
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                msg = self._chat(messages)
                content = THINK_RE.sub("", msg.get("content") or "").strip()
                calls = msg.get("tool_calls") or []
                messages.append({"role": "assistant", "content": content, "tool_calls": calls})
                if not calls:
                    break
                for call in calls:
                    fn = call.get("function", {})
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            args = {}
                    out = self.registry.execute(fn.get("name", ""), args, self.confirm)
                    messages.append({"role": "tool", "tool_name": fn.get("name", ""), "content": out})
                content = ""  # le texte final viendra du tour suivant
        except (requests.RequestException, OllamaError) as exc:
            log.error("Erreur Ollama : %s", exc)
            return "Désolé, mon cerveau local ne répond pas. Vérifiez qu'Ollama est lancé."

        reply = content or "C'est fait."
        self._remember(user_text, reply)
        return reply
