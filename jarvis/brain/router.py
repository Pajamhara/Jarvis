"""Chemin rapide : reconnaît les commandes courantes par règles, SANS appeler le modèle.

Avantages : réponse instantanée (< 50 ms) et 100 % fiable pour les demandes simples
(« ouvre YouTube », « monte le son », « minuteur de 10 minutes », « météo demain à Paris »...).
Tout ce qui n'est pas reconnu retourne None et est confié au modèle (Ollama).
"""
from __future__ import annotations

import difflib
import json
import logging
import re
from typing import Callable

from jarvis.textutils import normalize, words_to_number

log = logging.getLogger(__name__)

POLITE = re.compile(r"\b(s.il (?:te|vous) pla[iî]t|svp|stp|jarvis|merci)\b", re.I)

# « tu peux », « pourrais-tu », « je voudrais »... au début de la phrase
PREFIX = re.compile(
    r"^(?:(?:est[- ]ce que\s+)?(?:tu peux|peux[- ]tu|pourrais[- ]tu|tu pourrais|je voudrais|"
    r"j.aimerais|je veux|je souhaite)\s+(?:me\s+|m['’ ])?)+", re.I)

SETTINGS_RULES = [  # (motif sur le texte normalisé, page, libellé parlé)
    (r"applications par defaut", "applications_par_defaut", "des applications par défaut"),
    (r"wi ?fi|wifi", "wifi", "Wi-Fi"),
    (r"bluetooth", "bluetooth", "Bluetooth"),
    (r"affichage|ecran", "affichage", "d'affichage"),
    (r"\b(son|audio)\b", "son", "du son"),
    (r"batterie", "batterie", "de la batterie"),
    (r"mises? a jour|windows update|\bupdate\b", "mises_a_jour", "des mises à jour"),
    (r"confidentialite", "confidentialite", "de confidentialité"),
    (r"personnalisation|fond d ecran|theme", "personnalisation", "de personnalisation"),
    (r"notifications?", "notifications", "des notifications"),
    (r"stockage", "stockage", "de stockage"),
    (r"lumiere nocturne|night light", "lumiere_nocturne", "de la lumière nocturne"),
    (r"date|heure", "date_heure", "de date et d'heure"),
    (r"reseau|internet", "reseau", "du réseau"),
    (r"applications?|apps?", "applications", "des applications"),
    (r"comptes?", "comptes", "des comptes"),
]

CITY_RE = re.compile(
    r"\b(?:à|a|au|aux|de|du|pour|sur|en|dans)\s+([^\W\d_][\w' -]*?)"
    r"(?=\s+(?:demain|après[- ]demain|apres[- ]demain|aujourd'hui|aujourd hui|ce soir|ce matin|"
    r"cet après-midi|cet apres-midi|dans \d+ jours?)\b|\s*$)",
    re.I,
)
CITY_STOP = {"demain", "apres demain", "aujourd hui", "ce soir", "ce matin", "il", "elle",
             "jarvis", "moment", "ce moment"}
CITY_STOP_RE = re.compile(r"^(la|le|ce|cet|cette)\s+(semaine|week end|weekend|journee|soiree|matin|soir|moment|jour|nuit)")


class FastRouter:
    def __init__(self, config: dict, registry, confirm: Callable[[str], bool] | None = None) -> None:
        self.registry = registry
        self.confirm = confirm
        self.default_city = config["assistant"]["default_city"]
        self.apps = {normalize(k): k for k in config.get("apps", {})}
        self.sites = {normalize(k): (k, v) for k, v in config.get("sites", {}).items()}
        self.aliases = {normalize(k): normalize(v) for k, v in config.get("aliases", {}).items()}
        self.rules = [
            self._time, self._weather, self._reminder, self._timer, self._volume, self._media,
            self._power, self._settings, self._notes, self._memory, self._search, self._open,
        ]

    def route(self, text: str) -> str | None:
        """Retourne la réponse parlée si la demande est reconnue, sinon None."""
        orig = POLITE.sub(" ", text.lower())
        orig = re.sub(r"\s+", " ", re.sub(r"[?!.,;]", " ", orig)).strip()
        orig = PREFIX.sub("", orig).strip()
        t = normalize(orig)
        if not t:
            return None
        for rule in self.rules:
            reply = rule(t, orig)
            if reply is not None:
                log.info("Chemin rapide : %s", rule.__name__)
                return reply
        return None

    # ----------------------------------------------------------------- helpers
    def _run(self, name: str, args: dict | None = None) -> str:
        return self.registry.execute(name, args or {}, self.confirm)

    # -------------------------------------------------------------- heure/date
    def _time(self, t: str, orig: str) -> str | None:
        words = set(t.split())
        if len(words) > 7 or words & {"a", "au", "en", "dans", "pour", "tokyo", "new"}:
            return None
        ask_hour = re.search(r"\bquelle heure\b|\bheure est il\b", t)
        ask_date = re.search(r"\bquel jour\b|\bquelle date\b|\bquelle est la date\b|\bla date\b", t)
        if not (ask_hour or ask_date):
            return None
        now = self._run("get_datetime")  # "vendredi 20 novembre 2026, 14:05"
        day, _, hour = now.partition(", ")
        if ask_hour:
            return f"Il est {hour.replace(':', ' h ')}."
        return f"Nous sommes le {day}."

    # ------------------------------------------------------------------ météo
    def _weather(self, t: str, orig: str) -> str | None:
        if not (re.search(r"\bmeteo\b|\bquel temps\b|\b(pleuvoir|pleut|pleuvra)\b", t)):
            return None
        if re.search(r"\bapres demain\b", t):
            days = 2
        elif re.search(r"\bdemain\b", t):
            days = 1
        elif (m := re.search(r"\bdans (\d+) jours?\b", t)):
            days = min(int(m.group(1)), 6)
        else:
            days = 0

        city = self.default_city
        for m in CITY_RE.finditer(orig):
            cand = m.group(1).strip()
            n = normalize(cand)
            if n and n not in CITY_STOP and not CITY_STOP_RE.match(n):
                city = cand.title()
                break

        raw = self._run("get_weather", {"city": city, "days_ahead": days})
        try:
            d = json.loads(raw)
        except ValueError:
            return raw  # message d'erreur (ville introuvable, pas de réseau...)
        quand = {0: "Aujourd'hui", 1: "Demain", 2: "Après-demain"}.get(days, f"Dans {days} jours")
        reply = (f"{quand} à {d['ville']} : {d['conditions']}, "
                 f"de {round(d['temperature_min_c'])} à {round(d['temperature_max_c'])} degrés.")
        if (d.get("probabilite_pluie_pct") or 0) >= 30:
            reply += f" Risque de pluie : {round(d['probabilite_pluie_pct'])} pour cent."
        if days == 0 and "actuellement" in d:
            reply += f" Il fait actuellement {round(d['actuellement']['temperature_c'])} degrés."
        return reply

    # ----------------------------------------------------------------- durées
    @staticmethod
    def _parse_duration(t: str) -> tuple[int, bool]:
        """« 2 minutes 30 secondes », « vingt cinq minutes »... -> (secondes, a_des_heures)."""
        total, has_hours = 0, False
        for m in re.finditer(r"((?:\w+\s+){0,2}\w+)\s+(heures?|minutes?|mins?|secondes?|secs?)\b", t):
            tokens = m.group(1).split()
            n = None
            for k in range(len(tokens), 0, -1):  # plus long suffixe qui est un nombre
                n = words_to_number(tokens[-k:])
                if n is not None:
                    break
            if n is None:
                continue
            unit = m.group(2)
            if unit.startswith("heure"):
                total += n * 3600
                has_hours = True
            elif unit.startswith("min"):
                total += n * 60
            else:
                total += n
        return total, has_hours

    # ---------------------------------------------------------------- rappels
    def _reminder(self, t: str, orig: str) -> str | None:
        m = re.match(r"^(?:rappelle moi|rappelle nous|fais moi penser)\s+(.*)$", t)
        if not m:
            return None
        rest = m.group(1)
        args: dict = {}
        clock = re.search(r"\ba\s+(\d{1,2})\s*(?:h|heures?)\s*(\d{2})?\b", rest) or \
            re.search(r"\ba\s+(\w+)\s+heures?(?:\s+(\d{2}))?\b", rest)
        if clock and (hour := words_to_number([clock.group(1)])) is not None and hour < 24:
            args["at_time"] = f"{hour:02d}:{int(clock.group(2) or 0):02d}"
            rest = rest.replace(clock.group(0), " ")
        elif re.search(r"\bdans\b", rest):
            seconds, _ = self._parse_duration(rest)
            if seconds <= 0:
                return None
            args["in_minutes"] = round(seconds / 60, 2)
            rest = re.sub(r"\bdans\s+(?:\w+\s+){0,2}?\w+\s+(?:heures?|minutes?|mins?|secondes?|secs?)\b", " ", rest)
        else:
            return None
        label = re.sub(r"^(?:de|d|que|qu|pour)\s+", "", re.sub(r"\s+", " ", rest).strip())
        label = re.sub(r"^(?:de|d)\s+", "", label)
        args["label"] = label
        return self._run("set_reminder", args)

    # ------------------------------------------------------------ notes & mémoire
    def _notes(self, t: str, orig: str) -> str | None:
        if (m := re.match(r"^(?:prends?|prend) (?:en )?note(?: que| de| d')?\s*(.+)$", orig)) or \
           (m := re.match(r"^ajoute (?:une )?note(?: que| de| d')?\s*(.+)$", orig)) or \
           (m := re.match(r"^note(?: moi)?(?: que)\s+(.+)$", orig)):
            return self._run("add_note", {"text": m.group(1)})
        if re.search(r"\b(lis|relis|donne|montre|dis)\b.*\bnotes?\b|^mes notes$|\bquelles sont mes notes\b", t):
            return self._run("read_notes")
        return None

    def _memory(self, t: str, orig: str) -> str | None:
        if (m := re.match(r"^(?:retiens|memorise|mémorise|souviens toi|n oublie pas)(?: bien)?(?: que| de| d')?\s*(.+)$", orig)):
            return self._run("remember", {"fact": m.group(1)})
        if re.search(r"\b(oublie|efface)\b.*\b(tout|memoire|ce que tu sais)\b", t):
            return self._run("forget_memory")
        return None

    # ----------------------------------------------------------------- minuteur
    def _timer(self, t: str, orig: str) -> str | None:
        if not re.search(r"\bminuteur\b|\btimer\b|\bcompte a rebours\b", t):
            return None
        if re.search(r"\b(annule|arrete|supprime|stoppe|desactive)\b", t):
            return self._run("cancel_timers")

        total, matched_hours = self._parse_duration(t)
        if re.search(r"\bet demie?\b", t):
            total += 1800 if matched_hours else 30
        elif re.search(r"\bet quart\b", t):
            total += 900
        if total <= 0:
            return None  # durée non comprise : on laisse le modèle poser la question

        label = ""
        if (m := re.search(r"\bpour (?:les |la |le |l |mes |ma |mon |un |une )?([a-z][a-z ]*)$", t)):
            label = m.group(1).strip()
        return self._run("set_timer", {"seconds": total, "label": label})

    # ------------------------------------------------------------------ volume
    def _volume(self, t: str, orig: str) -> str | None:
        up = re.search(r"\b(monte|augmente|remonte|hausse)\b.*\b(son|volume)\b|\bplus fort\b", t)
        down = re.search(r"\b(baisse|diminue|reduis)\b.*\b(son|volume)\b|\bmoins fort\b|\bplus bas\b", t)
        mute = re.search(r"\b(coupe|mute|rends muet|remets|reactive|retablis)\b.*\bson\b|^mute$|\bsourdine\b", t)
        if not (up or down or mute):
            return None
        if mute and not (up or down):
            return self._run("volume_control", {"action": "mute"})
        steps = 5
        if (m := re.search(r"(\d+) pour cent", t)):
            steps = max(1, int(m.group(1)) // 2)
        elif re.search(r"\bun peu\b", t):
            steps = 3
        elif re.search(r"\bbeaucoup\b|\bnettement\b", t):
            steps = 15
        return self._run("volume_control", {"action": "up" if up else "down", "steps": steps})

    # ------------------------------------------------------------------ médias
    def _media(self, t: str, orig: str) -> str | None:
        noun = r"(morceau|piste|chanson|titre|musique)"
        if re.search(rf"\b{noun}\b.*\b(suivant|suivante|prochain|prochaine)\b|^(suivant|suivante|next)$|\bpasse\b.*\b(suivant|suivante)\b", t):
            return self._run("media_control", {"action": "next"})
        if re.search(rf"\b{noun}\b.*\b(precedent|precedente)\b|^(precedent|precedente)$", t):
            return self._run("media_control", {"action": "previous"})
        if re.search(
            r"^(pause|play|lecture)$|\b(mets|met|mettre) (la )?(musique |lecture )?en pause\b|"
            r"\b(reprends|reprend|relance)\b.*\b(lecture|musique)\b|"
            r"\b(pause|stop|arrete|coupe) (la )?(musique|lecture)\b", t):
            return self._run("media_control", {"action": "play_pause"})
        return None

    # ----------------------------------------------------------------- énergie
    def _power(self, t: str, orig: str) -> str | None:
        pc = r"\b(ordinateur|pc|machine|ordi)\b"
        if re.search(r"\bannule\b.*\b(extinction|arret|redemarrage)\b", t):
            return self._run("power_action", {"action": "cancel_shutdown"})
        if re.search(r"\b(eteins|eteindre|arrete)\b", t) and re.search(pc, t):
            return self._run("power_action", {"action": "shutdown"})  # confirmation imposée par l'outil
        if re.search(r"\b(redemarre|redemarrer|reboot)\b", t) and re.search(pc, t):
            return self._run("power_action", {"action": "restart"})
        if re.search(r"\bverrouille\b|\bverrouiller\b", t):
            return self._run("power_action", {"action": "lock"})
        return None

    # -------------------------------------------------------------- paramètres
    def _settings(self, t: str, orig: str) -> str | None:
        if not (re.search(r"\b(ouvre|ouvrir|affiche|va dans|lance|montre)\b", t)
                and re.search(r"\b(parametres?|reglages?)\b", t)):
            return None
        for pattern, page, label in SETTINGS_RULES:
            if re.search(pattern, t):
                self._run("open_settings", {"page": page})
                return f"J'ouvre les paramètres {label}."
        self._run("open_settings", {"page": "accueil"})
        return "J'ouvre les paramètres."

    # --------------------------------------------------------------- recherche
    def _search(self, t: str, orig: str) -> str | None:
        m = re.match(
            r"^(?:cherche|recherche|trouve)\s+(?:moi\s+)?(?:des?\s+|du\s+|la\s+|le\s+|les\s+)?(.+?)"
            r"(?:\s+(?:sur|dans|avec)\s+(youtube|google maps|google|wikipedia|wikipédia|maps|duckduckgo))?$",
            orig,
        )
        if not m or not m.group(1).strip():
            return None
        engine = normalize(m.group(2) or "google")
        engine = {"google maps": "maps"}.get(engine, engine)
        self._run("search_web", {"query": m.group(1).strip(), "engine": engine})
        return f"Je cherche {m.group(1).strip()} sur {engine}."

    # ------------------------------------------------------------ apps & sites
    def _open(self, t: str, orig: str) -> str | None:
        m = re.match(r"^(?:ouvre|ouvrir|lance|lancer|demarre|va sur|affiche)\s+(.+)$", t)
        if not m:
            return None
        drop = {"moi", "le", "la", "les", "l", "un", "une", "mon", "ma", "mes", "application",
                "appli", "app", "site", "page", "sur", "du", "de"}
        tokens = m.group(1).split()
        while tokens and tokens[0] in drop:
            tokens.pop(0)
        name = " ".join(tokens)
        if not name:
            return None
        name = self.aliases.get(name, name)

        key = name if name in self.apps else None
        if key is None:
            close = difflib.get_close_matches(name, list(self.apps), n=1, cutoff=0.8)
            key = close[0] if close else None
        if key is not None:
            result = self._run("open_app", {"name": self.apps[key]})
            return f"Je lance {self.apps[key]}." if result.endswith("lancée.") else result

        skey = name if name in self.sites else None
        if skey is None:
            close = difflib.get_close_matches(name, list(self.sites), n=1, cutoff=0.8)
            skey = close[0] if close else None
        if skey is not None:
            label, url = self.sites[skey]
            result = self._run("open_url", {"url": url})
            return f"J'ouvre {label}." if result.startswith("Page ouverte") else result

        if len(tokens) >= 2 and tokens[-1] in {"com", "fr", "org", "net", "io", "be", "ch"}:
            domain = "".join(tokens[:-1]) + "." + tokens[-1]
            result = self._run("open_url", {"url": domain})
            return f"J'ouvre {domain}." if result.startswith("Page ouverte") else result
        return None  # inconnu : le modèle décidera (ou dira que ce n'est pas autorisé)
