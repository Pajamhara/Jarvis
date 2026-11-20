"""Reconnaissance vocale (voix -> texte) avec faster-whisper, en local."""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


class SpeechToText:
    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "int8", language: str = "fr") -> None:
        from faster_whisper import WhisperModel

        log.info("Chargement du modèle Whisper '%s' (téléchargement au premier lancement)...", model_size)
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.language = language

    def transcribe(self, audio_int16: np.ndarray) -> str:
        audio = audio_int16.astype(np.float32) / 32768.0
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,                 # ignore les silences (évite les hallucinations)
            condition_on_previous_text=False,
            hotwords="Jarvis",
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
