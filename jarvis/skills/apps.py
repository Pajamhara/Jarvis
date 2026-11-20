"""Lancer des applications (uniquement celles de la liste blanche de config.yaml)."""
from __future__ import annotations

import difflib
import logging

from jarvis.brain.tools import Tool, ToolRegistry
from jarvis.skills import common

log = logging.getLogger(__name__)


def register(registry: ToolRegistry, config: dict) -> None:
    apps = {name.lower().strip(): target for name, target in config.get("apps", {}).items()}
    if not apps:
        return

    def open_app(name: str) -> str:
        key = name.lower().strip()
        if key not in apps:
            close = difflib.get_close_matches(key, list(apps), n=1, cutoff=0.7)
            if not close:
                return f"Application '{name}' absente de la liste autorisée. Disponibles : {', '.join(sorted(apps))}."
            key = close[0]
        try:
            common.launch(apps[key])
        except Exception as exc:
            log.warning("Échec du lancement de %s : %s", key, exc)
            return f"Impossible de lancer {key} (est-elle installée ?)."
        return f"{key} lancée."

    registry.register(
        Tool(
            name="open_app",
            description="Lance une application installée sur le PC (parmi la liste autorisée).",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "enum": sorted(apps), "description": "Nom de l'application"}
                },
                "required": ["name"],
            },
            func=open_app,
        )
    )
