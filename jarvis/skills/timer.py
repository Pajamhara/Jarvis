"""Minuteurs (non bloquants : Jarvis reste disponible pendant le décompte)."""
from __future__ import annotations

import datetime as dt
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
    def __init__(self, on_done: Callable[[str, str], None]) -> None:
        self.on_done = on_done
        self._timers: dict[int, threading.Timer] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def start(self, seconds: int, label: str, kind: str = "timer") -> None:
        with self._lock:
            tid = self._next_id
            self._next_id += 1
            timer = threading.Timer(seconds, self._fire, args=(tid, label, kind))
            timer.daemon = True
            self._timers[tid] = timer
            timer.start()

    def _fire(self, tid: int, label: str, kind: str) -> None:
        with self._lock:
            self._timers.pop(tid, None)
        try:
            self.on_done(label, kind)
        except Exception:
            log.exception("Erreur dans le rappel du minuteur")

    def cancel_all(self) -> int:
        with self._lock:
            n = len(self._timers)
            for t in self._timers.values():
                t.cancel()
            self._timers.clear()
        return n


def register(registry: ToolRegistry, config: dict, on_done: Callable[[str, str], None]) -> None:
    manager = TimerManager(on_done)

    def set_timer(minutes: float = 0, seconds: float = 0, label: str = "") -> str:
        total = int(minutes * 60 + seconds)
        if total <= 0:
            return "Durée invalide."
        if total > MAX_SECONDS:
            return "Durée trop longue (24 heures maximum)."
        manager.start(total, label)
        return f"Minuteur {label + ' ' if label else ''}de {human_duration(total)} démarré."

    def set_reminder(label: str = "", at_time: str = "", in_minutes: float = 0) -> str:
        """Rappel à une heure (HH:MM, prochaine occurrence) ou dans N minutes."""
        now = dt.datetime.now()
        if at_time:
            try:
                hh, mm = (int(x) for x in at_time.replace("h", ":").split(":")[:2])
                target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            except ValueError:
                return "Heure invalide."
            if target <= now:
                target += dt.timedelta(days=1)
            total = int((target - now).total_seconds())
            quand = f"à {target.strftime('%H:%M')}"
        elif in_minutes and in_minutes > 0:
            total = int(in_minutes * 60)
            quand = f"dans {human_duration(total)}"
        else:
            return "Il me faut une heure ou une durée."
        if total > MAX_SECONDS:
            return "Rappel trop lointain (24 heures maximum)."
        manager.start(total, label, kind="reminder")
        return f"Rappel programmé {quand}" + (f" : {label}." if label else ".") + \
            " Il sera perdu si je redémarre."

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
            name="set_reminder",
            description="Programme un rappel parlé à une heure donnée (ex : 18:30) ou dans N minutes.",
            input_schema={
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Ce dont il faut se souvenir"},
                    "at_time": {"type": "string", "description": "Heure au format HH:MM"},
                    "in_minutes": {"type": "number", "description": "Ou : dans N minutes"},
                },
                "required": ["label"],
            },
            func=set_reminder,
        )
    )
    registry.register(
        Tool(
            name="cancel_timers",
            description="Annule tous les minuteurs et rappels en cours.",
            input_schema={"type": "object", "properties": {}},
            func=cancel_timers,
        )
    )
