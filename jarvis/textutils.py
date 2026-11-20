"""Petits utilitaires de texte (normalisation, oui/non, nombres en toutes lettres)."""
from __future__ import annotations

import re
import unicodedata

YES_WORDS = {"oui", "ouais", "ok", "okay", "confirme", "accord", "affirmatif", "go"}
NO_WORDS = {"non", "annule", "stop", "negatif"}

_UNITS = {
    "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13,
    "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20, "trente": 30,
    "quarante": 40, "cinquante": 50, "soixante": 60,
}


def normalize(text: str) -> str:
    """minuscules, sans accents ni ponctuation : « Éteins-toi ! » -> « eteins toi »."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def is_yes(text: str) -> bool:
    words = set(normalize(text).split())
    return bool(words & YES_WORDS) and not (words & NO_WORDS)


def words_to_number(tokens: list[str]) -> int | None:
    """['vingt', 'cinq'] -> 25 ; ['10'] -> 10 ; sinon None."""
    if not tokens:
        return None
    total = 0
    for tok in tokens:
        if tok.isdigit():
            total += int(tok)
        elif tok in _UNITS:
            total += _UNITS[tok]
        elif tok == "et":
            continue
        else:
            return None
    return total
