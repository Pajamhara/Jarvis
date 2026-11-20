from jarvis.app import build_registry, is_yes, normalize
from jarvis.brain.tools import Tool, ToolRegistry
from jarvis.config import load_config
from jarvis.skills import apps, system, timer, weather, web


def test_config_defaults_and_merge():
    cfg = load_config()
    assert cfg["llm"]["model"]
    assert "navigateur" in cfg["apps"] and "youtube" in cfg["sites"]
    assert cfg["llm"]["base_url"].startswith("http://localhost")
    assert cfg["tts"]["engine"] in ("edge", "pyttsx3")


def test_normalize_and_yes():
    assert normalize("Éteins-toi, Jarvis !") == "eteins toi jarvis"
    assert is_yes("Oui, vas-y")
    assert not is_yes("non merci")
    assert not is_yes("peut-être")


def test_registry_unknown_and_error():
    reg = ToolRegistry()
    reg.register(Tool("boom", "", {"type": "object", "properties": {}}, lambda: 1 / 0))
    assert "inconnu" in reg.execute("nope", {})
    assert "Erreur" in reg.execute("boom", {})


def test_registry_confirmation():
    reg = ToolRegistry()
    ran = []
    reg.register(Tool("danger", "", {"type": "object", "properties": {}},
                      lambda: ran.append(1) or "fait", confirm_message=lambda a: "Sûr ?"))
    assert "annulée" in reg.execute("danger", {}, confirm=lambda q: False)
    assert not ran
    assert reg.execute("danger", {}, confirm=lambda q: True) == "fait"
    assert ran


def test_open_app_whitelist(monkeypatch):
    launched = []
    monkeypatch.setattr(apps.common, "launch", lambda t: launched.append(t))
    reg = ToolRegistry()
    apps.register(reg, {"apps": {"Bloc-Notes": "notepad.exe"}})
    assert "lancée" in reg.execute("open_app", {"name": "bloc-notes"})
    assert launched == ["notepad.exe"]
    assert "absente" in reg.execute("open_app", {"name": "format c:"})
    assert launched == ["notepad.exe"]


def test_url_validation(monkeypatch):
    opened = []
    monkeypatch.setattr(web.webbrowser, "open", lambda u: opened.append(u))
    assert web.normalize_url("youtube.com") == "https://youtube.com"
    reg = ToolRegistry()
    web.register(reg, {})
    assert "Erreur" in reg.execute("open_url", {"url": "file:///C:/Windows/system32"})
    assert "Erreur" in reg.execute("open_url", {"url": "javascript:alert(1)"})
    reg.execute("search_web", {"query": "crêpes", "engine": "youtube"})
    assert "search_query=cr%C3%AApes" in opened[-1]


def test_weather(monkeypatch):
    class Resp:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return self.payload

    def fake_get(url, params=None, timeout=None):
        if "geocoding" in url:
            return Resp({"results": [{"name": "Paris", "country": "France", "latitude": 48.85, "longitude": 2.35}]})
        return Resp({
            "current": {"temperature_2m": 11.0, "weather_code": 3, "wind_speed_10m": 9.0},
            "daily": {
                "time": ["2026-11-20", "2026-11-21"], "weather_code": [3, 61],
                "temperature_2m_max": [12, 10], "temperature_2m_min": [6, 7],
                "precipitation_probability_max": [10, 80], "precipitation_sum": [0, 4.2],
                "wind_speed_10m_max": [15, 25],
            },
        })

    monkeypatch.setattr(weather.requests, "get", fake_get)
    tomorrow = weather.get_weather("Paris", 1)
    assert tomorrow["conditions"] == "pluie faible" and tomorrow["temperature_max_c"] == 10
    assert "actuellement" not in tomorrow
    assert "actuellement" in weather.get_weather("Paris", 0)
    assert weather.get_weather("Paris", 99)["jours_depuis_aujourdhui"] == 1  # borné


def test_power_action_requires_confirmation_for_shutdown():
    assert system._power_confirmation({"action": "shutdown"})
    assert system._power_confirmation({"action": "restart"})
    assert system._power_confirmation({"action": "lock"}) is None


def test_timer_invalid():
    reg = ToolRegistry()
    timer.register(reg, {}, lambda label: None)
    assert "invalide" in reg.execute("set_timer", {})
    assert "démarré" in reg.execute("set_timer", {"seconds": 30, "label": "test"})
    assert "annulé" in reg.execute("cancel_timers", {})


def test_registry_coerces_small_model_arguments():
    reg = ToolRegistry()
    seen = {}
    reg.register(Tool("t", "", {"type": "object", "properties": {"n": {"type": "integer"}, "s": {"type": "string"}}},
                      lambda n=0, s="": seen.update(n=n, s=s) or "ok"))
    # "5" -> 5, 12 -> "12", paramètre inventé ignoré
    assert reg.execute("t", {"n": "5", "s": 12, "bidon": True}) == "ok"
    assert seen == {"n": 5, "s": "12"}
