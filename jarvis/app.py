"""Boucle principale : mot d'activation -> écoute -> (voix reconnue ?) -> STT -> cerveau -> TTS."""
from __future__ import annotations

import argparse
import logging
import sys
import threading

from jarvis.brain.llm import Brain
from jarvis.brain.tools import ToolRegistry
from jarvis.config import load_config
from jarvis.skills import apps, system, timer, weather, web
from jarvis.textutils import is_yes, normalize  # noqa: F401  (ré-exportés)

log = logging.getLogger("jarvis")

def build_registry(config: dict, on_timer_done) -> ToolRegistry:
    registry = ToolRegistry()
    apps.register(registry, config)
    web.register(registry, config)
    weather.register(registry, config)
    system.register(registry, config)
    timer.register(registry, config, on_timer_done)
    return registry


class Jarvis:
    def __init__(self, config: dict, text_mode: bool = False, speak: bool = False) -> None:
        self.cfg = config
        self.name = config["assistant"]["name"]
        self.text_mode = text_mode
        self._quit = False
        self._quit_phrases = [normalize(p) for p in config.get("quit_phrases", [])]

        self.tts = self.stt = self.wake = self.verifier = None

        if not text_mode or speak:
            from jarvis.core.tts import TextToSpeech

            t = config["tts"]
            self.tts = TextToSpeech(t["engine"], t["voice"], t["rate"])

        if not text_mode:
            from jarvis.core.stt import SpeechToText

            s = config["stt"]
            self.stt = SpeechToText(s["model_size"], s["device"], s["compute_type"], s["language"])

            w = config["wake_word"]
            if w["enabled"]:
                from jarvis.core.wake_word import WakeWordDetector

                self.wake = WakeWordDetector(w["model"], w["threshold"], config["audio"]["input_device"])

            sv = config["speaker_verification"]
            if sv["enabled"]:
                from jarvis.core.speaker_id import SpeakerVerifier

                self.verifier = SpeakerVerifier(sv["profile_path"], sv["threshold"], sv["min_duration"])

        self.registry = build_registry(config, self._on_timer_done)
        self.brain = Brain(config, self.registry, confirm=self.confirm)

        problem = self.brain.check()
        if problem:
            raise SystemExit(f"\n{problem}\n")
        threading.Thread(target=self.brain.warm_up, daemon=True).start()

    # ------------------------------------------------------------------ sortie
    def speak(self, text: str) -> None:
        print(f"{self.name} : {text}")
        if self.tts:
            self.tts.speak(text)

    def _on_timer_done(self, label: str) -> None:
        try:
            from jarvis.core.audio import beep

            for _ in range(3):
                beep(1000, 0.2)
        except Exception:
            pass
        title = self.cfg["assistant"].get("user_title") or ""
        what = f" « {label} »" if label else ""
        self.speak(f"{title + ', v' if title else 'V'}otre minuteur{what} est terminé.")

    # ----------------------------------------------------------------- entrée
    def _record(self, start_timeout: float):
        from jarvis.core.audio import record_utterance

        a = self.cfg["audio"]
        return record_utterance(
            device=a["input_device"],
            start_timeout=start_timeout,
            silence_duration=a["silence_duration"],
            max_duration=a["max_duration"],
            min_rms=a["min_rms"],
        )

    def confirm(self, question: str) -> bool:
        """Demande une confirmation orale (oui/non) avant une action sensible."""
        self.speak(question)
        if self.text_mode:
            return is_yes(input("(oui/non) > "))
        audio = self._record(start_timeout=6.0)
        if audio is None:
            return False
        text = self.stt.transcribe(audio)
        print(f"Vous : {text}")
        return is_yes(text)

    # ---------------------------------------------------------------- logique
    def _is_quit(self, text: str) -> bool:
        norm = normalize(text)
        return any(p and p in norm for p in self._quit_phrases)

    def _process_text(self, text: str) -> bool:
        """Retourne True si la conversation peut continuer."""
        if self._is_quit(text):
            self.speak("À bientôt.")
            self._quit = True
            return False
        self.speak(self.brain.respond(text))
        return True

    def _handle_audio(self, audio, verify: bool) -> bool:
        if verify and self.verifier is not None:
            ok, score = self.verifier.verify(audio)
            log.info("Vérification vocale : score %.2f -> %s", score, "OK" if ok else "refusé")
            if not ok:
                self.speak("Désolé, je ne reconnais pas votre voix.")
                return False
        text = self.stt.transcribe(audio)
        if not text:
            return False
        print(f"Vous : {text}")
        return self._process_text(text)

    def _wait_for_activation(self) -> None:
        if self.wake:
            log.info("En attente du mot d'activation (« Hey Jarvis »)...")
            self.wake.wait()
        else:
            input("\n[Entrée] pour parler... ")

    def _conversation(self) -> None:
        from jarvis.core.audio import beep

        beep()
        a = self.cfg["audio"]
        timeout, first = a["start_timeout"], True
        while not self._quit:
            audio = self._record(timeout)
            if audio is None:
                break
            # La voix n'est vérifiée qu'à la 1re phrase ; les suivantes (fenêtre de
            # conversation) sont considérées comme venant de la même personne.
            if not self._handle_audio(audio, verify=first):
                break
            first, timeout = False, a["follow_up_seconds"]

    # --------------------------------------------------------------- lancement
    def run(self) -> None:
        if self.text_mode:
            print("Mode texte. Tapez vos demandes (Ctrl+C pour quitter).")
            while not self._quit:
                text = input("\nVous > ").strip()
                if text:
                    self._process_text(text)
            return

        self.speak(f"{self.name} en ligne.")
        while not self._quit:
            self._wait_for_activation()
            if not self._quit:
                self._conversation()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis, assistant vocal personnel.")
    parser.add_argument("--config", help="Chemin d'un fichier config.yaml alternatif")
    parser.add_argument("--text", action="store_true", help="Mode texte (sans micro) pour tester")
    parser.add_argument("--speak", action="store_true", help="En mode texte, lire aussi les réponses à voix haute")
    parser.add_argument("--enroll", action="store_true", help="Enregistrer l'empreinte de votre voix")
    parser.add_argument("--list-devices", action="store_true", help="Lister les micros/haut-parleurs")
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs détaillés")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "urllib3", "faster_whisper"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    config = load_config(args.config)

    if args.list_devices:
        import sounddevice as sd

        print(sd.query_devices())
        return 0
    if args.enroll:
        from jarvis.core.speaker_id import enroll_interactive

        enroll_interactive(config)
        return 0

    try:
        Jarvis(config, text_mode=args.text, speak=args.speak).run()
    except (KeyboardInterrupt, EOFError):
        print("\nArrêt de Jarvis.")
    return 0
