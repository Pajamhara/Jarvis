"""Chargement de la configuration (config.yaml) avec valeurs par défaut."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import yaml

# Dans le .exe (PyInstaller), config.yaml / .env / data/ se trouvent À CÔTÉ de Jarvis.exe
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict[str, Any] = {
    "assistant": {"name": "Jarvis", "user_title": "", "default_city": "Paris"},
    "wake_word": {"enabled": True, "model": "hey_jarvis", "threshold": 0.5},
    "audio": {
        "input_device": None,
        "start_timeout": 6.0,
        "follow_up_seconds": 6.0,
        "silence_duration": 1.0,
        "max_duration": 20.0,
        "min_rms": 350,
    },
    "stt": {
        "model_size": "small",
        "device": "auto",
        "compute_type": "int8",
        "language": "fr",
    },
    "tts": {"engine": "edge", "voice": "fr-FR-HenriNeural", "rate": "+0%"},
    "speaker_verification": {
        "enabled": False,
        "threshold": 0.75,
        "min_duration": 1.0,
        "profile_path": "data/voiceprint.npy",
    },
    "llm": {"model": "claude-haiku-5-5", "max_tokens": 600, "history_turns": 8},
    "quit_phrases": ["au revoir jarvis", "eteins toi", "arrete toi", "quitte jarvis"],
    "apps": {},
}


def _merge(base: dict, override: dict) -> dict:
    """Fusionne récursivement `override` dans `base`."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULTS)
    path = Path(path) if path else ROOT / "config.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        _merge(cfg, user_cfg)
    return cfg


def resolve_path(p: str | Path) -> Path:
    """Chemin relatif -> relatif à la racine du projet."""
    p = Path(p)
    return p if p.is_absolute() else ROOT / p
