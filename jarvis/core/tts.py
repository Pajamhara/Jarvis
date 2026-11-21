"""Synthèse vocale : Piper (local, très rapide) -> edge-tts (en ligne) -> pyttsx3 (Windows, hors ligne).

Chaque moteur qui échoue passe automatiquement la main au suivant.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

from jarvis.config import resolve_path

log = logging.getLogger(__name__)

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"


def clean_for_speech(text: str) -> str:
    """Retire le markdown et les caractères qui se lisent mal à voix haute."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def piper_urls(name: str) -> tuple[str, str]:
    """'fr_FR-tom-medium' -> URL du .onnx et du .onnx.json sur HuggingFace."""
    code, voice, quality = name.split("-", 2)
    base = f"{PIPER_BASE}/{code.split('_')[0]}/{code}/{voice}/{quality}/{name}"
    return base + ".onnx", base + ".onnx.json"


def _download(url: str, dest) -> None:
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for block in r.iter_content(1 << 20):
                f.write(block)
    tmp.replace(dest)


class TextToSpeech:
    def __init__(self, engine: str = "piper", voice: str = "fr-FR-HenriNeural",
                 rate: str = "+0%", piper_voice: str = "fr_FR-tom-medium") -> None:
        self.engine = engine
        self.voice = voice
        self.rate = rate
        self.piper_voice = piper_voice
        self.last_latency = 0.0                         # durée de synthèse du dernier message
        self.on_audio_start: Callable[[], None] | None = None
        self._lock = threading.Lock()                   # un seul message parlé à la fois
        self._cancel = threading.Event()
        self._piper = None
        self._broken: set[str] = set()                  # moteurs en panne : on ne réessaie pas

    # ------------------------------------------------------------- contrôle
    def stop(self) -> None:
        """Coupe la parole en cours (et les phrases qui suivent) — clic sur l'orbe."""
        self._cancel.set()
        try:
            sd.stop()
        except Exception:
            pass

    def reset(self) -> None:
        self._cancel.clear()

    # ------------------------------------------------------------------ API
    def speak(self, text: str) -> None:
        text = clean_for_speech(text)
        if not text or self._cancel.is_set():
            return
        with self._lock:
            if self._cancel.is_set():
                return
            order = {"piper": ["piper", "edge", "pyttsx3"], "edge": ["edge", "pyttsx3"]}.get(
                self.engine, ["pyttsx3"])
            for name in order:
                if name in self._broken:
                    continue
                try:
                    getattr(self, f"_speak_{name}")(text)
                    return
                except Exception as exc:
                    log.warning("Voix '%s' indisponible (%s) -> moteur suivant.", name, exc)
                    self._broken.add(name)

    # ------------------------------------------------------------- lecture
    def _play(self, audio: np.ndarray, sample_rate: int, t0: float) -> None:
        self.last_latency = time.monotonic() - t0
        if self.on_audio_start:
            self.on_audio_start()
        sd.play(audio, sample_rate)
        sd.wait()

    # --------------------------------------------------------------- Piper
    def _load_piper(self):
        from piper import PiperVoice

        onnx_url, json_url = piper_urls(self.piper_voice)
        folder = resolve_path("data/voices")
        onnx = folder / f"{self.piper_voice}.onnx"
        if not onnx.exists():
            log.info("Téléchargement de la voix Piper '%s' (une seule fois)...", self.piper_voice)
            _download(json_url, folder / f"{self.piper_voice}.onnx.json")
            _download(onnx_url, onnx)
        return PiperVoice.load(str(onnx))

    def _speak_piper(self, text: str) -> None:
        t0 = time.monotonic()
        if self._piper is None:
            self._piper = self._load_piper()
        chunks = list(self._piper.synthesize(text))
        audio = np.concatenate([c.audio_float_array for c in chunks]).astype(np.float32)
        rate = getattr(chunks[0], "sample_rate", None) or self._piper.config.sample_rate
        self._play(audio, int(rate), t0)

    # ----------------------------------------------------------------- edge
    def _speak_edge(self, text: str) -> None:
        import edge_tts
        import soundfile as sf

        t0 = time.monotonic()
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            asyncio.run(edge_tts.Communicate(text, self.voice, rate=self.rate).save(path))
            data, sr = sf.read(path, dtype="float32")
            self._play(data, sr, t0)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    # -------------------------------------------------------------- pyttsx3
    def _speak_pyttsx3(self, text: str) -> None:
        import pyttsx3

        self.last_latency = 0.0
        if self.on_audio_start:
            self.on_audio_start()
        engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            blob = f"{v.id} {v.name} {getattr(v, 'languages', '')}".lower()
            if "fr" in blob or "french" in blob or "fran" in blob:
                engine.setProperty("voice", v.id)
                break
        engine.say(text)
        engine.runAndWait()
        engine.stop()
