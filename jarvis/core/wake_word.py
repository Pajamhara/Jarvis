"""Détection du mot d'activation avec openWakeWord (local, en continu)."""
from __future__ import annotations

import logging

import sounddevice as sd

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
FRAME = 1280  # 80 ms : taille de bloc attendue par openWakeWord


class WakeWordDetector:
    def __init__(self, model_name: str = "hey_jarvis", threshold: float = 0.5,
                 device: int | str | None = None) -> None:
        from openwakeword.model import Model

        self.threshold = threshold
        self.device = device
        try:
            self.model = Model(wakeword_models=[model_name], inference_framework="onnx")
        except Exception:  # modèles pas encore téléchargés
            log.info("Téléchargement des modèles openWakeWord (première utilisation)...")
            import openwakeword

            openwakeword.utils.download_models()
            self.model = Model(wakeword_models=[model_name], inference_framework="onnx")

    def wait(self) -> None:
        """Bloque jusqu'à ce que le mot d'activation soit entendu."""
        self.model.reset()
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME, device=self.device
        ) as stream:
            while True:
                data, _ = stream.read(FRAME)
                scores = self.model.predict(data[:, 0])
                if scores and max(scores.values()) >= self.threshold:
                    log.debug("Mot d'activation détecté : %s", scores)
                    return
