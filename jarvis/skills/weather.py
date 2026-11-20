"""Météo via Open-Meteo (gratuit, sans clé API)."""
from __future__ import annotations

import requests

from jarvis.brain.tools import Tool, ToolRegistry

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Codes météo WMO -> description française
WMO = {
    0: "ciel dégagé", 1: "plutôt dégagé", 2: "partiellement nuageux", 3: "ciel couvert",
    45: "brouillard", 48: "brouillard givrant",
    51: "bruine légère", 53: "bruine", 55: "bruine forte",
    56: "bruine verglaçante légère", 57: "bruine verglaçante forte",
    61: "pluie faible", 63: "pluie modérée", 65: "pluie forte",
    66: "pluie verglaçante légère", 67: "pluie verglaçante forte",
    71: "neige faible", 73: "neige modérée", 75: "neige forte", 77: "grains de neige",
    80: "averses faibles", 81: "averses modérées", 82: "averses violentes",
    85: "averses de neige faibles", 86: "averses de neige fortes",
    95: "orage", 96: "orage avec grêle", 99: "orage violent avec grêle",
}


def get_weather(city: str, days_ahead: int = 0) -> dict | str:
    geo = requests.get(
        GEOCODING_URL,
        params={"name": city, "count": 1, "language": "fr", "format": "json"},
        timeout=10,
    )
    geo.raise_for_status()
    results = geo.json().get("results")
    if not results:
        return f"Ville introuvable : {city}"
    place = results[0]

    forecast = requests.get(
        FORECAST_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,precipitation_sum,wind_speed_10m_max",
            "timezone": "auto",
            "forecast_days": 7,
        },
        timeout=10,
    )
    forecast.raise_for_status()
    data = forecast.json()
    daily = data["daily"]

    i = max(0, min(int(days_ahead), len(daily["time"]) - 1))
    out: dict = {
        "ville": place["name"],
        "pays": place.get("country", ""),
        "date": daily["time"][i],
        "jours_depuis_aujourdhui": i,
        "conditions": WMO.get(daily["weather_code"][i], "conditions inconnues"),
        "temperature_max_c": daily["temperature_2m_max"][i],
        "temperature_min_c": daily["temperature_2m_min"][i],
        "probabilite_pluie_pct": daily["precipitation_probability_max"][i],
        "cumul_pluie_mm": daily["precipitation_sum"][i],
        "vent_max_kmh": daily["wind_speed_10m_max"][i],
    }
    if i == 0 and "current" in data:
        cur = data["current"]
        out["actuellement"] = {
            "temperature_c": cur["temperature_2m"],
            "conditions": WMO.get(cur["weather_code"], "inconnues"),
            "vent_kmh": cur["wind_speed_10m"],
        }
    return out


def register(registry: ToolRegistry, config: dict) -> None:
    default_city = config["assistant"]["default_city"]

    def tool(city: str = "", days_ahead: int = 0):
        return get_weather(city or default_city, days_ahead)

    registry.register(
        Tool(
            name="get_weather",
            description="Donne la météo d'une ville : aujourd'hui, demain ou jusqu'à 6 jours à l'avance.",
            input_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Nom de la ville (vide = ville par défaut)"},
                    "days_ahead": {
                        "type": "integer", "minimum": 0, "maximum": 6,
                        "description": "0 = aujourd'hui, 1 = demain, 2 = après-demain...",
                    },
                },
            },
            func=tool,
        )
    )
