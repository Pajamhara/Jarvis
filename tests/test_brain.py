import requests

from jarvis.app import build_registry
from jarvis.brain import llm
from jarvis.brain.llm import Brain
from jarvis.config import load_config


class Resp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.text = payload, status, str(payload)

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.text)


def make_brain(**llm_cfg):
    cfg = load_config()
    cfg["llm"].update({"stream": False, **llm_cfg})
    return Brain(cfg, build_registry(cfg, lambda label, kind='timer': None))


def test_fast_path_skips_model(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("modèle appelé")))
    brain = make_brain()
    assert brain.respond("quelle heure est-il ?").startswith("Il est")
    assert len(brain.history) == 2


def test_model_tool_loop(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None, stream=False):
        calls.append(json)
        if len(calls) == 1:  # le modèle demande l'heure via un outil (arguments en str, comme certains modèles)
            return Resp({"message": {"role": "assistant", "content": "",
                                     "tool_calls": [{"function": {"name": "get_datetime", "arguments": "{}"}}]}})
        assert json["messages"][-1]["role"] == "tool"
        return Resp({"message": {"role": "assistant", "content": "<think>hm</think>Il est bientôt midi."}})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    brain = make_brain(fast_path=False)
    assert brain.respond("dis-moi l'heure en phrase") == "Il est bientôt midi."
    assert len(calls) == 2 and calls[0]["think"] is False
    assert {"get_weather", "open_app"} <= {t["function"]["name"] for t in calls[0]["tools"]}
    assert brain.history[-1]["content"] == "Il est bientôt midi."


def test_retry_without_think_param(monkeypatch):
    seen = []

    def fake_post(url, json=None, timeout=None, stream=False):
        seen.append("think" in json)
        if "think" in json:
            return Resp({"error": "model does not support think"}, status=400)
        return Resp({"message": {"role": "assistant", "content": "Bonjour."}})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert make_brain(fast_path=False).respond("bonjour") == "Bonjour."
    assert seen == [True, False]


def test_ollama_down(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("refusé")

    monkeypatch.setattr(llm.requests, "post", boom)
    monkeypatch.setattr(llm.requests, "get", boom)
    brain = make_brain(fast_path=False)
    assert "Ollama" in brain.respond("bonjour")
    assert "Ollama ne répond pas" in brain.check()


def test_check_missing_model(monkeypatch):
    monkeypatch.setattr(llm.requests, "get", lambda *a, **k: Resp({"models": [{"name": "autre:7b"}]}))
    assert "ollama pull qwen3.5:9b" in make_brain().check()
    monkeypatch.setattr(llm.requests, "get", lambda *a, **k: Resp({"models": [{"name": "qwen3.5:9b"}]}))
    assert make_brain().check() is None


class StreamResp:
    status_code = 200
    text = ""

    def __init__(self, pieces, tool_calls=None):
        import json as _json
        lines = [_json.dumps({"message": {"role": "assistant", "content": p}, "done": False}) for p in pieces]
        if tool_calls:
            lines.insert(1, _json.dumps({"message": {"role": "assistant", "content": "", "tool_calls": tool_calls}, "done": False}))
        lines.append(_json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}))
        self._lines = [l.encode() for l in lines]

    def iter_lines(self):
        return iter(self._lines)


def test_streaming_speaks_first_sentence_then_rest(monkeypatch):
    pieces = ["Bonjour, ", "je suis là.", " Que puis-", "je faire ", "pour vous ?"]
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: StreamResp(pieces))
    said = []
    brain = make_brain(fast_path=False, stream=True)
    reply = brain.respond("salut", on_sentence=said.append)
    assert said == ["Bonjour, je suis là.", "Que puis-je faire pour vous ?"]
    assert reply == "Bonjour, je suis là. Que puis-je faire pour vous ?"
    assert brain.last_streamed is True


def test_streaming_short_reply_is_left_to_caller(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: StreamResp(["D'accord."]))
    said = []
    brain = make_brain(fast_path=False, stream=True)
    assert brain.respond("ok", on_sentence=said.append) == "D'accord."
    assert said == [] and brain.last_streamed is False  # l'appelant dira la réponse


def test_streaming_tool_call_is_not_spoken(monkeypatch):
    answers = [
        StreamResp(["Je regarde l'heure maintenant."], tool_calls=[{"function": {"name": "get_datetime", "arguments": {}}}]),
        StreamResp(["Il est ", "midi pile. ", "Bon appétit !"]),
    ]
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: answers.pop(0))
    said = []
    brain = make_brain(fast_path=False, stream=True)
    reply = brain.respond("heure en phrase", on_sentence=said.append)
    assert reply == "Il est midi pile. Bon appétit !"
    assert said[-2:] == ["Il est midi pile.", "Bon appétit !"]


def test_memory_in_prompt(monkeypatch):
    monkeypatch.setattr(llm, "read_facts", lambda: ["son chat s'appelle Mochi"])
    assert "Mochi" in make_brain()._system()
