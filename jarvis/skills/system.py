"""Actions système : heure, paramètres Windows, volume, médias, verrouillage/extinction."""
from __future__ import annotations

import datetime as dt
import subprocess

from jarvis.brain.tools import Tool, ToolRegistry
from jarvis.skills.common import IS_WINDOWS, NOT_WINDOWS_MSG, launch

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

# Nom que Jarvis peut utiliser -> URI de la page de Paramètres Windows
SETTINGS_PAGES = {
    "accueil": "ms-settings:",
    "wifi": "ms-settings:network-wifi",
    "reseau": "ms-settings:network",
    "bluetooth": "ms-settings:bluetooth",
    "affichage": "ms-settings:display",
    "son": "ms-settings:sound",
    "batterie": "ms-settings:batterysaver",
    "applications": "ms-settings:appsfeatures",
    "applications_par_defaut": "ms-settings:defaultapps",
    "mises_a_jour": "ms-settings:windowsupdate",
    "confidentialite": "ms-settings:privacy",
    "personnalisation": "ms-settings:personalization",
    "notifications": "ms-settings:notifications",
    "stockage": "ms-settings:storagesense",
    "comptes": "ms-settings:yourinfo",
    "lumiere_nocturne": "ms-settings:nightlight",
    "date_heure": "ms-settings:dateandtime",
}

# Codes des touches virtuelles Windows
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
VK_MEDIA_NEXT, VK_MEDIA_PREV, VK_MEDIA_PLAY_PAUSE = 0xB0, 0xB1, 0xB3
KEYEVENTF_KEYUP = 0x0002


def _press(vk: int, times: int = 1) -> None:
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def get_datetime() -> str:
    now = dt.datetime.now()
    return f"{JOURS[now.weekday()]} {now.day} {MOIS[now.month - 1]} {now.year}, {now.strftime('%H:%M')}"


def open_settings(page: str = "accueil") -> str:
    if not IS_WINDOWS:
        return NOT_WINDOWS_MSG
    uri = SETTINGS_PAGES.get(page)
    if uri is None:
        return f"Page de paramètres inconnue : {page}"
    launch(uri)
    return f"Paramètres ouverts : {page}."


def volume_control(action: str, steps: int = 5) -> str:
    if not IS_WINDOWS:
        return NOT_WINDOWS_MSG
    steps = max(1, min(int(steps), 50))  # 1 appui = 2 % de volume
    if action == "up":
        _press(VK_VOLUME_UP, steps)
        return f"Volume augmenté d'environ {steps * 2} %."
    if action == "down":
        _press(VK_VOLUME_DOWN, steps)
        return f"Volume baissé d'environ {steps * 2} %."
    if action == "mute":
        _press(VK_VOLUME_MUTE)
        return "Son coupé / rétabli."
    return f"Action de volume inconnue : {action}"


def media_control(action: str) -> str:
    if not IS_WINDOWS:
        return NOT_WINDOWS_MSG
    keys = {"play_pause": VK_MEDIA_PLAY_PAUSE, "next": VK_MEDIA_NEXT, "previous": VK_MEDIA_PREV}
    if action not in keys:
        return f"Commande média inconnue : {action}"
    _press(keys[action])
    return "C'est fait."


def power_action(action: str) -> str:
    if not IS_WINDOWS:
        return NOT_WINDOWS_MSG
    commands = {
        "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
        "shutdown": ["shutdown", "/s", "/t", "20"],   # 20 s de délai : annulable
        "restart": ["shutdown", "/r", "/t", "20"],
        "cancel_shutdown": ["shutdown", "/a"],
    }
    if action not in commands:
        return f"Action inconnue : {action}"
    subprocess.run(commands[action], check=False)
    return {
        "lock": "Session verrouillée.",
        "shutdown": "Extinction dans 20 secondes (dites-moi d'annuler pour l'arrêter).",
        "restart": "Redémarrage dans 20 secondes (dites-moi d'annuler pour l'arrêter).",
        "cancel_shutdown": "Extinction annulée.",
    }[action]


def _power_confirmation(args: dict) -> str | None:
    """Extinction / redémarrage : demandent TOUJOURS une confirmation vocale."""
    return {
        "shutdown": "Voulez-vous vraiment éteindre l'ordinateur ?",
        "restart": "Voulez-vous vraiment redémarrer l'ordinateur ?",
    }.get(args.get("action", ""))


def register(registry: ToolRegistry, config: dict) -> None:
    registry.register(Tool(
        name="get_datetime",
        description="Donne la date et l'heure actuelles.",
        input_schema={"type": "object", "properties": {}},
        func=get_datetime,
    ))
    registry.register(Tool(
        name="open_settings",
        description="Ouvre une page des Paramètres Windows.",
        input_schema={
            "type": "object",
            "properties": {"page": {"type": "string", "enum": sorted(SETTINGS_PAGES)}},
            "required": ["page"],
        },
        func=open_settings,
    ))
    registry.register(Tool(
        name="volume_control",
        description="Règle le volume du PC : monter, baisser ou couper/rétablir le son. "
                    "Un 'step' = environ 2 % (5 steps ≈ 10 %).",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["up", "down", "mute"]},
                "steps": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["action"],
        },
        func=volume_control,
    ))
    registry.register(Tool(
        name="media_control",
        description="Contrôle la lecture multimédia : pause/lecture, piste suivante ou précédente.",
        input_schema={
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["play_pause", "next", "previous"]}},
            "required": ["action"],
        },
        func=media_control,
    ))
    registry.register(Tool(
        name="power_action",
        description="Verrouille la session, éteint ou redémarre le PC (avec confirmation vocale), "
                    "ou annule une extinction programmée.",
        input_schema={
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["lock", "shutdown", "restart", "cancel_shutdown"]}},
            "required": ["action"],
        },
        func=power_action,
        confirm_message=_power_confirmation,
    ))
