"""Synthèse vocale (texte -> voix) : edge-tts (neuronal) avec repli pyttsx3 (hors ligne)."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import threading

import sounddevice as sd

log = logging.getLogger(__name__)


def clean_for_speech(text: str) -> str:
    """Retire le markdown et les caractères qui se lisent mal à voix haute."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class TextToSpeech:
    def __init__(self, engine: str = "edge", voice: str = "fr-FR-HenriNeural",
                 rate: str = "+0%") -> None:
        self.engine = engine
        self.voice = voice
        self.rate = rate
        self._lock = threading.Lock()  # un seul message parlé à la fois (minuteurs inclus)

    def speak(self, text: str) -> None:
        text = clean_for_speech(text)
        if not text:
            return
        with self._lock:
            if self.engine == "edge":
                try:
                    self._speak_edge(text)
                    return
                except Exception as exc:  # pas d'internet, etc.
                    log.warning("edge-tts indisponible (%s), repli sur pyttsx3.", exc)
            self._speak_pyttsx3(text)

    def _speak_edge(self, text: str) -> None:
        import edge_tts
        import soundfile as sf

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            asyncio.run(edge_tts.Communicate(text, self.voice, rate=self.rate).save(path))
            data, sr = sf.read(path, dtype="float32")
            sd.play(data, sr)
            sd.wait()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def _speak_pyttsx3(self, text: str) -> None:
        import pyttsx3

        engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            blob = f"{v.id} {v.name} {getattr(v, 'languages', '')}".lower()
            if "fr" in blob or "french" in blob or "fran" in blob:
                engine.setProperty("voice", v.id)
                break
        engine.say(text)
        engine.runAndWait()
        engine.stop()
