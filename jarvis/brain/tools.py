"""Registre d'outils : ce que Jarvis a le droit de faire.

Chaque outil = un nom, une description (lue par le LLM), un schéma JSON des
paramètres et une fonction Python. Le LLM choisit l'outil, mais c'est CE code
qui décide ce qui s'exécute réellement (liste blanche + confirmation).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger(__name__)

ConfirmFn = Callable[[str], bool]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    func: Callable[..., Any]
    # Si défini : renvoie la question à poser à voix haute avant d'exécuter
    # (ou None si aucune confirmation n'est nécessaire pour ces arguments).
    confirm_message: Callable[[dict], str | None] | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        """Définitions au format attendu par l'API Claude."""
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]

    def execute(self, name: str, args: dict, confirm: ConfirmFn | None = None) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Outil inconnu : {name}"

        if tool.confirm_message is not None:
            question = tool.confirm_message(args)
            if question and not (confirm and confirm(question)):
                log.info("Action '%s' non confirmée, annulée.", name)
                return "Action annulée : l'utilisateur n'a pas confirmé."

        try:
            log.info("Outil : %s(%s)", name, args)
            result = tool.func(**args)
        except Exception as exc:  # on ne plante jamais l'assistant à cause d'un outil
            log.exception("Erreur dans l'outil %s", name)
            return f"Erreur lors de l'exécution de {name} : {exc}"
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
