"""Vérification du locuteur : n'obéir qu'à VOTRE voix (optionnel).

Utilise Resemblyzer : chaque extrait de voix est converti en une "empreinte"
(vecteur de 256 nombres). On compare l'empreinte de la phrase entendue à celle
enregistrée lors de `python main.py --enroll` (similarité cosinus).
"""
from __future__ import annotations

import logging

import numpy as np

from jarvis.config import resolve_path

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000

ENROLL_PHRASES = [
    "Jarvis, quel temps fera-t-il demain à Paris ?",
    "Ouvre le navigateur et lance ma musique, s'il te plaît.",
    "Baisse un peu le volume, puis mets un minuteur de dix minutes.",
    "Quelle heure est-il, et quel jour sommes-nous aujourd'hui ?",
    "Ouvre les paramètres du Wi-Fi et dis-moi si tout fonctionne bien.",
]


def _load_encoder():
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav
    except ImportError as exc:
        raise RuntimeError(
            "Resemblyzer n'est pas installé. Voir la section « Reconnaissance de votre voix » du README."
        ) from exc
    return VoiceEncoder(verbose=False), preprocess_wav


def _embed(encoder, preprocess_wav, audio_int16: np.ndarray, min_samples: int):
    wav = preprocess_wav(audio_int16.astype(np.float32) / 32768.0, source_sr=SAMPLE_RATE)
    if len(wav) < min_samples:
        return None
    return encoder.embed_utterance(wav)


class SpeakerVerifier:
    def __init__(self, profile_path: str, threshold: float = 0.75, min_duration: float = 1.0) -> None:
        self.encoder, self._preprocess = _load_encoder()
        self.threshold = threshold
        self.min_samples = int(min_duration * SAMPLE_RATE)
        path = resolve_path(profile_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Aucune empreinte vocale trouvée ({path}). Lancez d'abord : python main.py --enroll"
            )
        self.profile = np.load(path)

    def verify(self, audio_int16: np.ndarray) -> tuple[bool, float]:
        """Retourne (est_ce_vous, score_de_similarité)."""
        emb = _embed(self.encoder, self._preprocess, audio_int16, self.min_samples)
        if emb is None:  # trop court / trop silencieux pour juger
            return False, 0.0
        score = float(np.dot(emb, self.profile))
        return score >= self.threshold, score


def enroll_interactive(config: dict) -> None:
    """Assistant en console : enregistre 5 phrases, calcule et sauvegarde l'empreinte."""
    from jarvis.core.audio import record_utterance

    sv = config["speaker_verification"]
    a = config["audio"]
    encoder, preprocess = _load_encoder()
    min_samples = int(sv["min_duration"] * SAMPLE_RATE)

    def capture(prompt: str):
        for _ in range(3):
            input(prompt)
            audio = record_utterance(
                device=a["input_device"], start_timeout=8.0, silence_duration=1.2,
                max_duration=15.0, min_rms=a["min_rms"],
            )
            if audio is None:
                print("  -> Je n'ai rien entendu, on réessaie.")
                continue
            emb = _embed(encoder, preprocess, audio, min_samples)
            if emb is None:
                print("  -> Trop court, parlez un peu plus longtemps.")
                continue
            return emb
        raise RuntimeError("Impossible d'obtenir un enregistrement exploitable (vérifiez votre micro).")

    print("=== Enregistrement de votre voix ===")
    print("Parlez naturellement, dans les conditions où vous utiliserez Jarvis.\n")
    embeddings = []
    for i, phrase in enumerate(ENROLL_PHRASES, 1):
        embeddings.append(capture(f"[{i}/{len(ENROLL_PHRASES)}] Entrée, puis lisez : « {phrase} »\n"))
        print("  OK.")

    profile = np.mean(embeddings, axis=0)
    profile /= np.linalg.norm(profile)
    path = resolve_path(sv["profile_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, profile)
    print(f"\nEmpreinte enregistrée : {path}")

    print("\n=== Test : dites 3 phrases libres pour voir les scores ===")
    scores = []
    for i in range(3):
        emb = capture(f"[test {i + 1}/3] Entrée, puis dites une phrase libre : ")
        scores.append(float(np.dot(emb, profile)))
        print(f"  Similarité : {scores[-1]:.2f}")
    suggestion = round(max(0.6, min(scores) - 0.05), 2)
    print(f"\nSeuil conseillé pour config.yaml (speaker_verification.threshold) : {suggestion}")
    print("Puis passez `speaker_verification.enabled` à true.")
