"""Boucle principale : mot d'activation -> écoute -> (voix reconnue ?) -> STT -> cerveau -> TTS."""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
import threading
import time

from jarvis.brain.llm import Brain
from jarvis.brain.tools import ToolRegistry
from jarvis.config import load_config, resolve_path
from jarvis.skills import apps, memory, system, timer, weather, web, websearch
from jarvis.textutils import is_yes, normalize  # noqa: F401  (ré-exportés)

log = logging.getLogger("jarvis")


def build_registry(config: dict, on_timer_done) -> ToolRegistry:
    registry = ToolRegistry()
    apps.register(registry, config)
    web.register(registry, config)
    websearch.register(registry, config)
    weather.register(registry, config)
    system.register(registry, config)
    memory.register(registry, config)
    timer.register(registry, config, on_timer_done)
    return registry


class Jarvis:
    def __init__(self, config: dict, text_mode: bool = False, speak: bool = False) -> None:
        self.cfg = config
        self.name = config["assistant"]["name"]
        self.text_mode = text_mode
        self._quit = False
        self._quit_phrases = [normalize(p) for p in config.get("quit_phrases", [])]
        self.ui = None
        self._turn: dict = {}  # chronométrage du tour de parole en cours

        self.tts = self.stt = self.wake = self.verifier = None

        if not text_mode or speak:
            from jarvis.core.tts import TextToSpeech

            t = config["tts"]
            self.tts = TextToSpeech(t["engine"], t["voice"], t["rate"], t["piper_voice"])
            self.tts.on_audio_start = self._on_audio_start

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

    # ---------------------------------------------------------------- interface
    def _state(self, state: str) -> None:
        if self.ui is not None:
            self.ui.set_state(state)

    def stop_speaking(self) -> None:
        if self.tts:
            self.tts.stop()

    # ------------------------------------------------------------------ sortie
    def speak(self, text: str) -> None:
        print(f"{self.name} : {text}")
        if self.tts:
            if "end_record" in self._turn:
                self._turn.setdefault("first_speak", time.monotonic())
            self._state("speaking")
            self.tts.speak(text)

    def _on_audio_start(self) -> None:
        """Appelé quand le son va démarrer : affiche le détail du temps de réaction."""
        t = self._turn
        if "end_record" not in t or "first_speak" not in t or t.get("logged"):
            return
        t["logged"] = True
        now = time.monotonic()
        synth = self.tts.last_latency if self.tts else 0.0
        log.info("⏱  %.1f s entre la fin de votre phrase et la voix "
                 "(transcription %.1f s · cerveau %.1f s · synthèse %.1f s)",
                 now - t["end_record"], t.get("stt", 0.0),
                 max(0.0, t["first_speak"] - t["end_record"] - t.get("stt", 0.0)), synth)

    def _on_timer_done(self, label: str, kind: str = "timer") -> None:
        try:
            from jarvis.core.audio import beep

            for _ in range(3):
                beep(1000, 0.2)
        except Exception:
            pass
        title = self.cfg["assistant"].get("user_title") or ""
        head = f"{title}, " if title else ""
        if kind == "reminder":
            self.speak(f"{head}rappel : {label}." if label else f"{head}c'est l'heure de votre rappel.")
        else:
            what = f" « {label} »" if label else ""
            self.speak(f"{head}votre minuteur{what} est terminé.")

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
        self._state("listening")
        audio = self._record(start_timeout=6.0)
        if audio is None:
            return False
        self._state("thinking")
        text = self.stt.transcribe(audio)
        print(f"Vous : {text}")
        return is_yes(text)

    # ---------------------------------------------------------------- logique
    def _is_quit(self, text: str) -> bool:
        norm = normalize(text)
        return any(p and p in norm for p in self._quit_phrases)

    def _process_text(self, text: str) -> bool:
        """Retourne True si la conversation peut continuer."""
        if self.tts:
            self.tts.reset()
        if self._is_quit(text):
            self.speak("À bientôt.")
            self._quit = True
            return False
        t0 = time.monotonic()
        stream_cb = self.speak if self.tts else None  # la 1re phrase est dite avant la fin de la génération
        reply = self.brain.respond(text, on_sentence=stream_cb)
        if not self.brain.last_streamed:
            self.speak(reply)
        if self.text_mode:
            log.info("⏱  cerveau : %.1f s", time.monotonic() - t0)
        return True

    def _handle_audio(self, audio, verify: bool) -> bool:
        self._turn = {"end_record": time.monotonic()}
        self._state("thinking")
        if verify and self.verifier is not None:
            ok, score = self.verifier.verify(audio)
            log.info("Vérification vocale : score %.2f -> %s", score, "OK" if ok else "refusé")
            if not ok:
                self.speak("Désolé, je ne reconnais pas votre voix.")
                return False
        t0 = time.monotonic()
        text = self.stt.transcribe(audio)
        self._turn["stt"] = time.monotonic() - t0
        if not text:
            return False
        print(f"Vous : {text}")
        return self._process_text(text)

    def _wait_for_activation(self) -> None:
        self._state("idle")
        if self.wake:
            log.info("En attente du mot d'activation (« Hey Jarvis »)...")
            self.wake.wait()
        else:
            input("\n[Entrée] pour parler... ")

    def _conversation(self) -> None:
        from jarvis.core.audio import beep

        self._state("listening")
        beep()
        a = self.cfg["audio"]
        timeout, first = a["start_timeout"], True
        while not self._quit:
            self._state("listening")
            audio = self._record(timeout)
            if audio is None:
                break
            # La voix n'est vérifiée qu'à la 1re phrase ; les suivantes (fenêtre de
            # conversation) sont considérées comme venant de la même personne.
            if not self._handle_audio(audio, verify=first):
                break
            first, timeout = False, a["follow_up_seconds"]
        self._state("idle")

    # --------------------------------------------------------------- lancement
    def _voice_loop(self) -> None:
        self.speak(f"{self.name} en ligne.")
        while not self._quit:
            self._wait_for_activation()
            if not self._quit:
                self._conversation()

    def _voice_loop_guarded(self) -> None:
        try:
            self._voice_loop()
        except Exception:
            log.exception("Erreur dans la boucle vocale")
            self._state("error")
            time.sleep(3)
        finally:
            if self.ui is not None:
                self.ui.close()

    def run(self) -> None:
        if self.text_mode:
            print("Mode texte. Tapez vos demandes (Ctrl+C pour quitter).")
            while not self._quit:
                text = input("\nVous > ").strip()
                if text:
                    self._process_text(text)
            return

        ui_cfg = self.cfg["ui"]
        if ui_cfg["orb"]:
            try:
                from jarvis.ui.orb import Orb

                self.ui = Orb(self.name, ui_cfg["size"], on_quit=self._request_quit,
                              on_stop=self.stop_speaking)
            except Exception as exc:  # pas d'écran, Tk absent...
                log.warning("Orbe indisponible (%s) : mode console seul.", exc)

        if self.ui is None:
            self._voice_loop()
            return

        # L'interface doit tourner dans le thread principal ; l'assistant, dans un thread à part.
        threading.Thread(target=self._voice_loop_guarded, daemon=True).start()
        self.ui.run()
        self._quit = True
        logging.shutdown()
        os._exit(0)  # coupe proprement le thread audio resté en attente du micro

    def _request_quit(self) -> None:
        self._quit = True
        self.stop_speaking()


def _setup_logging(verbose: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        log_file = resolve_path("data/jarvis.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=2, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    for noisy in ("httpx", "httpcore", "urllib3", "faster_whisper", "huggingface_hub",
                  "filelock", "hpack", "PIL", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis, assistant vocal personnel.")
    parser.add_argument("--config", help="Chemin d'un fichier config.yaml alternatif")
    parser.add_argument("--text", action="store_true", help="Mode texte (sans micro) pour tester")
    parser.add_argument("--speak", action="store_true", help="En mode texte, lire aussi les réponses à voix haute")
    parser.add_argument("--enroll", action="store_true", help="Enregistrer l'empreinte de votre voix")
    parser.add_argument("--list-devices", action="store_true", help="Lister les micros/haut-parleurs")
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs détaillés")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
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
