import json

import pytest

from jarvis.brain.router import FastRouter
from jarvis.config import load_config


class FakeRegistry:
    """Enregistre les appels d'outils et renvoie des réponses typiques."""
    def __init__(self):
        self.calls = []

    def execute(self, name, args, confirm=None):
        self.calls.append((name, args))
        if name == "get_datetime":
            return "vendredi 20 novembre 2026, 14:05"
        if name == "get_weather":
            return json.dumps({
                "ville": args["city"], "conditions": "pluie faible",
                "temperature_min_c": 7.2, "temperature_max_c": 10.4,
                "probabilite_pluie_pct": 80, "actuellement": {"temperature_c": 9.0},
            })
        if name == "open_app":
            return f"{args['name']} lancée."
        if name == "open_url":
            return f"Page ouverte : {args['url']}"
        return "ok"


@pytest.fixture
def router():
    reg = FakeRegistry()
    return FastRouter(load_config(), reg), reg


def last(reg):
    return reg.calls[-1]


def test_open_site_and_app(router):
    r, reg = router
    assert r.route("Ouvre YouTube") == "J'ouvre youtube."
    assert last(reg) == ("open_url", {"url": "https://www.youtube.com"})
    assert r.route("lance la calculatrice, s'il te plaît") == "Je lance calculatrice."
    assert last(reg) == ("open_app", {"name": "calculatrice"})
    assert r.route("ouvre spotify") == "Je lance spotify."
    assert r.route("ouvre youtube.com")  # domaine dicté
    assert r.route("Ouvre un truc inconnu") is None  # laissé au modèle


def test_settings(router):
    r, reg = router
    assert r.route("Ouvre les paramètres Wi-Fi") == "J'ouvre les paramètres Wi-Fi."
    assert last(reg) == ("open_settings", {"page": "wifi"})
    r.route("ouvre les paramètres de mise à jour")
    assert last(reg)[1] == {"page": "mises_a_jour"}
    r.route("ouvre les paramètres")
    assert last(reg)[1] == {"page": "accueil"}


def test_weather_city_and_day(router):
    r, reg = router
    reply = r.route("Quel temps fera-t-il demain à Paris ?")
    assert last(reg) == ("get_weather", {"city": "Paris", "days_ahead": 1})
    assert reply.startswith("Demain à Paris : pluie faible, de 7 à 10 degrés.")
    assert "80 pour cent" in reply
    r.route("quel temps fait-il à New York")
    assert last(reg) == ("get_weather", {"city": "New York", "days_ahead": 0})
    r.route("la météo")  # ville par défaut
    assert last(reg) == ("get_weather", {"city": "Paris", "days_ahead": 0})
    r.route("météo de demain")
    assert last(reg)[1] == {"city": "Paris", "days_ahead": 1}
    r.route("est-ce qu'il va pleuvoir après-demain à Lyon")
    assert last(reg) == ("get_weather", {"city": "Lyon", "days_ahead": 2})


@pytest.mark.parametrize("phrase,seconds,label", [
    ("Mets un minuteur de 10 minutes", 600, ""),
    ("minuteur de vingt cinq minutes", 1500, ""),
    ("lance un minuteur d'une heure et demie", 5400, ""),
    ("minuteur 2 minutes 30 secondes pour les pâtes", 150, "pates"),
])
def test_timer(router, phrase, seconds, label):
    r, reg = router
    r.route(phrase)
    assert last(reg) == ("set_timer", {"seconds": seconds, "label": label})


def test_timer_cancel_and_unclear(router):
    r, reg = router
    r.route("annule le minuteur")
    assert last(reg)[0] == "cancel_timers"
    assert r.route("mets un minuteur") is None  # durée absente -> le modèle demandera


def test_volume_and_media(router):
    r, reg = router
    r.route("monte le son")
    assert last(reg) == ("volume_control", {"action": "up", "steps": 5})
    r.route("baisse un peu le volume")
    assert last(reg) == ("volume_control", {"action": "down", "steps": 3})
    r.route("monte le son de 20 pour cent")
    assert last(reg)[1]["steps"] == 10
    r.route("coupe le son")
    assert last(reg) == ("volume_control", {"action": "mute"})
    r.route("passe à la chanson suivante")
    assert last(reg) == ("media_control", {"action": "next"})
    r.route("mets en pause")
    assert last(reg) == ("media_control", {"action": "play_pause"})


def test_power_goes_through_tool_confirmation(router):
    r, reg = router
    r.route("éteins l'ordinateur")
    assert last(reg) == ("power_action", {"action": "shutdown"})
    r.route("verrouille le PC")
    assert last(reg) == ("power_action", {"action": "lock"})


def test_time_and_search(router):
    r, reg = router
    assert r.route("quelle heure est-il ?") == "Il est 14 h 05."
    assert r.route("quel jour sommes-nous") == "Nous sommes le vendredi 20 novembre 2026."
    assert r.route("quelle heure est-il à Tokyo") is None  # fuseau : laissé au modèle
    r.route("cherche des recettes de crêpes sur YouTube")
    assert last(reg) == ("search_web", {"query": "recettes de crêpes", "engine": "youtube"})


def test_unknown_goes_to_model(router):
    r, _ = router
    for phrase in ["raconte-moi une blague", "qui a gagné la coupe du monde 2018", "bonjour"]:
        assert r.route(phrase) is None


def test_polite_prefix_and_aliases(router):
    r, reg = router
    assert r.route("peux-tu lancer la calculette") == "Je lance calculatrice."
    assert r.route("ouvre mon navigateur") == "Je lance navigateur."
    assert r.route("je voudrais ouvrir les paramètres bluetooth") == "J'ouvre les paramètres Bluetooth."
    assert last(reg) == ("open_settings", {"page": "bluetooth"})
    r.route("ouvre internet")
    assert last(reg) == ("open_app", {"name": "navigateur"})
    r.route("lance yt")
    assert last(reg) == ("open_url", {"url": "https://www.youtube.com"})


def test_notes_and_memory(router):
    r, reg = router
    r.route("prends en note que j'ai rendez-vous chez le dentiste jeudi")
    assert last(reg) == ("add_note", {"text": "j'ai rendez-vous chez le dentiste jeudi"})
    r.route("ajoute une note acheter du lait")
    assert last(reg) == ("add_note", {"text": "acheter du lait"})
    r.route("lis mes notes")
    assert last(reg)[0] == "read_notes"
    r.route("retiens que mon chat s'appelle Mochi")
    assert last(reg) == ("remember", {"fact": "mon chat s'appelle mochi"})
    r.route("oublie tout ce que tu sais")
    assert last(reg)[0] == "forget_memory"


def test_reminders(router):
    r, reg = router
    r.route("rappelle-moi à 18h30 d'appeler maman")
    assert last(reg) == ("set_reminder", {"at_time": "18:30", "label": "appeler maman"})
    r.route("rappelle moi à huit heures de prendre mon médicament")
    assert last(reg)[1]["at_time"] == "08:00" and "medicament" in last(reg)[1]["label"].replace("é", "e")
    r.route("rappelle-moi dans 20 minutes de sortir le gratin")
    assert last(reg) == ("set_reminder", {"in_minutes": 20.0, "label": "sortir le gratin"})
    assert r.route("rappelle-moi de ...") is None  # pas d'heure : le modèle demandera
