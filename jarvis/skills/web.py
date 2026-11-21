"""Ouvrir des pages web et lancer des recherches dans le navigateur par défaut."""
from __future__ import annotations

import re
import webbrowser
from urllib.parse import quote_plus, urlparse

from jarvis.brain.tools import Tool, ToolRegistry

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "wikipedia": "https://fr.wikipedia.org/w/index.php?search={q}",
    "maps": "https://www.google.com/maps/search/{q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
}


def normalize_url(url: str) -> str:
    """Ajoute https:// si besoin et n'accepte que des URL http(s) valides."""
    url = url.strip()
    if "://" not in url:
        # "javascript:...", "mailto:...", "file:..." -> refusés (seul "site.com:8080" est un hôte:port)
        if re.match(r"^[a-z][a-z0-9+.\-]*:(?!\d)", url, re.IGNORECASE):
            raise ValueError(f"URL non autorisée : {url}")
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"URL non autorisée : {url}")
    parsed.port  # lève ValueError si le port est invalide
    return url


def open_url(url: str) -> str:
    url = normalize_url(url)
    webbrowser.open(url)
    return f"Page ouverte : {url}"


def search_web(query: str, engine: str = "google") -> str:
    template = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"])
    url = template.format(q=quote_plus(query))
    webbrowser.open(url)
    return f"Recherche '{query}' ouverte sur {engine}."


def register(registry: ToolRegistry, config: dict) -> None:
    registry.register(
        Tool(
            name="open_url",
            description=(
                "Ouvre une page web dans le navigateur par défaut. Pour un site connu "
                "(YouTube, Gmail, Netflix...), déduis son adresse officielle."
            ),
            input_schema={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Adresse, ex : https://www.youtube.com"}},
                "required": ["url"],
            },
            func=open_url,
        )
    )
    registry.register(
        Tool(
            name="search_web",
            description="OUVRE la page de résultats dans le navigateur (Google, YouTube, Wikipédia, Maps...) quand l'utilisateur veut VOIR la page.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Termes de la recherche"},
                    "engine": {"type": "string", "enum": sorted(SEARCH_ENGINES), "description": "Moteur (défaut : google)"},
                },
                "required": ["query"],
            },
            func=search_web,
        )
    )
