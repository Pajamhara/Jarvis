"""Utilitaires partagés par les compétences."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

IS_WINDOWS = sys.platform == "win32"
NOT_WINDOWS_MSG = "Cette action n'est disponible que sous Windows."


def launch(target: Any) -> None:
    """Lance une application, un fichier ou une URI (ex : 'notepad.exe', 'spotify:').

    `target` peut être une chaîne ou un dict {path: ..., args: [...]}.
    Jamais de shell=True : pas d'injection de commande possible.
    """
    if isinstance(target, dict):
        subprocess.Popen([target["path"], *map(str, target.get("args", []))])
        return
    target = str(target)
    if IS_WINDOWS:
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])
