"""Mémoire à long terme (faits retenus) et notes dictées. Fichiers dans data/ (jamais publiés)."""
from __future__ import annotations

import datetime as dt
import json
import logging

from jarvis.brain.tools import Tool, ToolRegistry
from jarvis.config import resolve_path

log = logging.getLogger(__name__)
MAX_FACTS = 50
MAX_LEN = 300


def data_dir():
    return resolve_path("data")


def _facts_file():
    return data_dir() / "memory.json"


def _notes_file():
    return data_dir() / "notes.txt"


def read_facts() -> list[str]:
    try:
        return [str(f) for f in json.loads(_facts_file().read_text(encoding="utf-8"))]
    except (OSError, ValueError):
        return []


def _write_facts(facts: list[str]) -> None:
    path = _facts_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(facts[-MAX_FACTS:], ensure_ascii=False, indent=1), encoding="utf-8")


def remember(fact: str) -> str:
    fact = fact.strip()[:MAX_LEN]
    if not fact:
        return "Rien à retenir."
    facts = read_facts()
    if fact not in facts:
        facts.append(fact)
        _write_facts(facts)
    return "C'est noté, je m'en souviendrai."


def forget_memory() -> str:
    _write_facts([])
    return "Ma mémoire a été effacée."


def add_note(text: str) -> str:
    text = " ".join(text.split())[:1000]
    if not text:
        return "Note vide."
    path = _notes_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M} — {text}\n")
    return "Note enregistrée."


def read_notes(count: int = 5) -> str:
    try:
        lines = [l.strip() for l in _notes_file().read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        lines = []
    if not lines:
        return "Vous n'avez aucune note."
    last = lines[-max(1, min(int(count), 10)):]
    return "Vos dernières notes : " + " ; ".join(l.split(" — ", 1)[-1] for l in last) + "."


def register(registry: ToolRegistry, config: dict) -> None:
    obj = {"type": "object", "properties": {}}
    registry.register(Tool(
        "remember", "Retient un fait durable sur l'utilisateur (ex : 'son chat s'appelle Mochi'). "
                    "À utiliser quand il dit « retiens que... ».",
        {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}, remember))
    registry.register(Tool(
        "forget_memory", "Efface tout ce que Jarvis a retenu sur l'utilisateur.", obj, forget_memory,
        confirm_message=lambda args: "Voulez-vous vraiment effacer ma mémoire ?"))
    registry.register(Tool(
        "add_note", "Ajoute une note dictée au carnet de notes.",
        {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}, add_note))
    registry.register(Tool(
        "read_notes", "Lit les dernières notes du carnet.",
        {"type": "object", "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 10}}},
        read_notes))
