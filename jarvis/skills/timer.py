"""Minuteurs (non bloquants : Jarvis reste disponible pendant le décompte)."""
from __future__ import annotations

import logging
import threading
from typing import Callable

from jarvis.brain.tools import Tool, ToolRegistry

log = logging.getLogger(__name__)
MAX_SECONDS = 24 * 3600


def human_duration(seconds: int) -> str:
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    parts = []
    if h:
        parts.append(f"{h} heure{'s' if h > 1 else ''}")
    if m:
        parts.append(f"{m} minute{'s' if m > 1 else ''}")
    if s:
        parts.append(f"{s} seconde{'s' if s > 1 else ''}")
    return " ".join(parts) or "0 seconde"


class TimerManager:
    def __init__(self, on_done: Callable[[str], None]) -> None:
        self.on_done = on_done
        self._timers: dict[int, threading.Timer] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def start(self, seconds: int, label: str) -> None:
        with self._lock:
            tid = self._next_id
            self._next_id += 1
            timer = threading.Timer(seconds, self._fire, args=(tid, label))
            timer.daemon = True
            self._timers[tid] = timer
            timer.start()

    def _fire(self, tid: int, label: str) -> None:
        with self._lock:
            self._timers.pop(tid, None)
        try:
            self.on_done(label)
        except Exception:
            log.exception("Erreur dans le rappel du minuteur")

    def cancel_all(self) -> int:
        with self._lock:
            n = len(self._timers)
            for t in self._timers.values():
                t.cancel()
            self._timers.clear()
        return n


def register(registry: ToolRegistry, config: dict, on_done: Callable[[str], None]) -> None:
    manager = TimerManager(on_done)

    def set_timer(minutes: float = 0, seconds: float = 0, label: str = "") -> str:
        total = int(minutes * 60 + seconds)
        if total <= 0:
            return "Durée invalide."
        if total > MAX_SECONDS:
            return "Durée trop longue (24 heures maximum)."
        manager.start(total, label)
        return f"Minuteur {label + ' ' if label else ''}de {human_duration(total)} démarré."

    def cancel_timers() -> str:
        n = manager.cancel_all()
        return f"{n} minuteur(s) annulé(s)." if n else "Aucun minuteur en cours."

    registry.register(
        Tool(
            name="set_timer",
            description="Démarre un minuteur ; Jarvis préviendra à voix haute à la fin.",
            input_schema={
                "type": "object",
                "properties": {
                    "minutes": {"type": "number", "description": "Minutes"},
                    "seconds": {"type": "number", "description": "Secondes"},
                    "label": {"type": "string", "description": "Nom facultatif (ex : 'pâtes')"},
                },
            },
            func=set_timer,
        )
    )
    registry.register(
        Tool(
            name="cancel_timers",
            description="Annule tous les minuteurs en cours.",
            input_schema={"type": "object", "properties": {}},
            func=cancel_timers,
        )
    )
