import sys
import types

import pytest

from jarvis.skills import memory, websearch


# ------------------------------------------------------------ mémoire & notes
@pytest.fixture
def datadir(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "data_dir", lambda: tmp_path)
    return tmp_path


def test_facts_roundtrip(datadir):
    assert memory.read_facts() == []
    memory.remember("son chat s'appelle Mochi")
    memory.remember("son chat s'appelle Mochi")  # pas de doublon
    memory.remember("il habite à Lyon")
    assert memory.read_facts() == ["son chat s'appelle Mochi", "il habite à Lyon"]
    assert "effacée" in memory.forget_memory()
    assert memory.read_facts() == []


def test_facts_are_bounded(datadir):
    for i in range(80):
        memory.remember(f"fait {i}")
    assert len(memory.read_facts()) == memory.MAX_FACTS
    assert memory.read_facts()[-1] == "fait 79"


def test_notes(datadir):
    assert "aucune note" in memory.read_notes()
    memory.add_note("acheter   du lait")
    memory.add_note("appeler maman")
    out = memory.read_notes()
    assert "acheter du lait" in out and "appeler maman" in out
    assert "20" in (datadir / "notes.txt").read_text(encoding="utf-8")  # horodatage


def test_forget_requires_confirmation(datadir):
    from jarvis.brain.tools import ToolRegistry

    reg = ToolRegistry()
    memory.register(reg, {})
    memory.remember("secret")
    assert "annulée" in reg.execute("forget_memory", {}, confirm=lambda q: False)
    assert memory.read_facts() == ["secret"]
    reg.execute("forget_memory", {}, confirm=lambda q: True)
    assert memory.read_facts() == []


# ------------------------------------------------------------- recherche web
def test_lookup_online(monkeypatch):
    fake = types.ModuleType("ddgs")

    class DDGS:
        def text(self, query, region=None, max_results=None):
            assert region == "fr-fr"
            return [{"title": "Titre", "href": "http://x", "body": "Corps du résultat. " * 50}]

    fake.DDGS = DDGS
    monkeypatch.setitem(sys.modules, "ddgs", fake)
    out = websearch.lookup_online("météo")
    assert "DONNÉES" in out and "Titre" in out and len(out) < 700


def test_lookup_online_failures(monkeypatch):
    monkeypatch.setitem(sys.modules, "ddgs", None)  # import impossible
    assert "pas disponible" in websearch.lookup_online("x")

    fake = types.ModuleType("ddgs")

    class Boom:
        def text(self, *a, **k):
            raise RuntimeError("rate limit")

    fake.DDGS = Boom
    monkeypatch.setitem(sys.modules, "ddgs", fake)
    assert "échoué" in websearch.lookup_online("x")


# ------------------------------------------------------------------- voix
@pytest.fixture
def tts_module(monkeypatch):
    """Importe jarvis.core.tts avec un faux `sounddevice` (pas de carte son en CI)."""
    played = []
    sd = types.ModuleType("sounddevice")
    sd.play = lambda audio, sr: played.append((len(audio), sr))
    sd.wait = lambda: None
    sd.stop = lambda: played.append("stop")
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.delitem(sys.modules, "jarvis.core.tts", raising=False)
    import jarvis.core.tts as tts

    return tts, played


def test_piper_url():
    sd = types.ModuleType("sounddevice")
    sys.modules.setdefault("sounddevice", sd)
    from jarvis.core.tts import piper_urls

    onnx, js = piper_urls("fr_FR-tom-medium")
    assert onnx.endswith("/fr/fr_FR/tom/medium/fr_FR-tom-medium.onnx")
    assert js.endswith("fr_FR-tom-medium.onnx.json")


def test_tts_fallback_chain(tts_module):
    tts, played = tts_module
    t = tts.TextToSpeech(engine="piper")
    calls = []

    def boom(name):
        def f(text):
            calls.append(name)
            raise RuntimeError(name)
        return f

    t._speak_piper = boom("piper")
    t._speak_edge = boom("edge")
    t._speak_pyttsx3 = lambda text: calls.append("pyttsx3")
    t.speak("Bonjour")
    assert calls == ["piper", "edge", "pyttsx3"]
    t.speak("Encore")          # les moteurs en panne ne sont pas réessayés
    assert calls == ["piper", "edge", "pyttsx3", "pyttsx3"]


def test_tts_stop_cancels_following_sentences(tts_module):
    tts, played = tts_module
    t = tts.TextToSpeech(engine="pyttsx3")
    said = []
    t._speak_pyttsx3 = said.append
    t.speak("Première phrase.")
    t.stop()
    t.speak("Deuxième phrase.")   # ignorée après un stop
    assert said == ["Première phrase."] and "stop" in played
    t.reset()
    t.speak("Nouvelle demande.")
    assert said[-1] == "Nouvelle demande."


def test_tts_cleans_markdown(tts_module):
    tts, _ = tts_module
    assert tts.clean_for_speech("**Bonjour** https://x.fr `ok`") == "Bonjour ok"
