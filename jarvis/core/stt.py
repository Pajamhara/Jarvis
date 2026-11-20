"""Reconnaissance vocale (voix -> texte) avec faster-whisper, sur GPU NVIDIA si possible."""
from __future__ import annotations

import logging

import numpy as np

from jarvis.core.cuda_setup import setup_cuda_dlls

log = logging.getLogger(__name__)


class SpeechToText:
    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "float16", language: str = "fr") -> None:
        setup_cuda_dlls()
        from faster_whisper import WhisperModel

        self.language = language
        self.model = None

        if device in ("auto", "cuda"):
            try:
                log.info("Chargement de Whisper '%s' sur GPU (%s)...", model_size, compute_type)
                self.model = WhisperModel(model_size, device="cuda", compute_type=compute_type)
                self._transcribe(np.zeros(16_000, dtype=np.float32))  # test réel : cuBLAS chargé ?
                log.info("Whisper tourne sur le GPU.")
            except Exception as exc:  # DLL manquantes, carte non supportée, VRAM pleine...
                log.warning("GPU indisponible pour Whisper (%s) -> repli sur le processeur.", exc)
                self.model = None

        if self.model is None:
            log.info("Chargement de Whisper '%s' sur processeur (int8)...", model_size)
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def _transcribe(self, audio_f32: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio_f32,
            language=self.language,
            beam_size=5,
            vad_filter=True,                 # ignore les silences (évite les hallucinations)
            condition_on_previous_text=False,
            hotwords="Jarvis",
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def transcribe(self, audio_int16: np.ndarray) -> str:
        return self._transcribe(audio_int16.astype(np.float32) / 32768.0)
