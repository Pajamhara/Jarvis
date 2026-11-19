"""Capture micro : détection de parole (VAD simple basé sur l'énergie) et bip."""
from __future__ import annotations

import time
from collections import deque

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000


def rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))


def beep(freq: int = 880, duration: float = 0.12, volume: float = 0.2) -> None:
    """Petit bip pour signaler que Jarvis écoute."""
    sr = 44_100
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    tone = (volume * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    tone *= np.linspace(1.0, 0.0, len(tone), dtype=np.float32)  # évite le "clic" final
    sd.play(tone, sr)
    sd.wait()


def record_utterance(
    sample_rate: int = SAMPLE_RATE,
    device: int | str | None = None,
    start_timeout: float = 6.0,
    silence_duration: float = 1.0,
    max_duration: float = 20.0,
    min_rms: float = 350.0,
    max_rms: float = 1500.0,
) -> np.ndarray | None:
    """Enregistre une phrase.

    Attend que vous parliez (max `start_timeout` s), enregistre jusqu'à
    `silence_duration` s de silence. Retourne un tableau int16 mono,
    ou None si personne n'a parlé.
    """
    chunk = int(sample_rate * 0.05)  # blocs de 50 ms
    chunk_dur = chunk / sample_rate

    with sd.InputStream(
        samplerate=sample_rate, channels=1, dtype="int16", blocksize=chunk, device=device
    ) as stream:
        # 1) Calibrage rapide du bruit ambiant (200 ms)
        noise = [rms(stream.read(chunk)[0][:, 0]) for _ in range(4)]
        threshold = min(max(min_rms, float(np.median(noise)) * 3.0), max_rms)

        pre_roll: deque[np.ndarray] = deque(maxlen=4)  # garde le tout début de la phrase
        frames: list[np.ndarray] = []
        speaking = False
        silent_for = 0.0
        t0 = time.monotonic()
        speech_t0 = t0

        # 2) Boucle de capture
        while True:
            data, _ = stream.read(chunk)
            mono = data[:, 0].copy()
            level = rms(mono)
            now = time.monotonic()

            if not speaking:
                pre_roll.append(mono)
                if level > threshold:
                    speaking = True
                    speech_t0 = now
                    frames.extend(pre_roll)
                elif now - t0 > start_timeout:
                    return None
            else:
                frames.append(mono)
                silent_for = 0.0 if level > threshold else silent_for + chunk_dur
                if silent_for >= silence_duration or now - speech_t0 > max_duration:
                    break

    audio = np.concatenate(frames)
    if len(audio) / sample_rate < 0.3:  # simple bruit / claquement
        return None
    return audio
