import logging
from typing import Optional, List, Dict

import requests

from config import AVIASALES_TOKEN

CITY_SEARCH_URL = "https://api.travelpayouts.com/places2"
FLIGHT_SEARCH_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

logger = logging.getLogger(__name__)


def search_iata(city: str) -> Optional[str]:
    """Return IATA code for the city using Aviasales API."""
    if not AVIASALES_TOKEN:
        logger.error("AVIASALES_TOKEN is not set")
        return None
    params = {
        "term": city,
        "locale": "ru",
        "types[]": "city",
        "token": AVIASALES_TOKEN,
    }
    try:
        resp = requests.get(CITY_SEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return data[0].get("code")
    except Exception as e:
        logger.exception("Failed to fetch IATA code: %s", e)
    return None


def search_flights(origin: str, destination: str, date: str) -> List[Dict]:
    """Return list of flights for given parameters."""
    if not AVIASALES_TOKEN:
        logger.error("AVIASALES_TOKEN is not set")
        return []
    origin_code = search_iata(origin)
    destination_code = search_iata(destination)
    if not origin_code or not destination_code:
        logger.error("Unknown city for flight search: %s -> %s", origin, destination)
        return []

    params = {
        "origin": origin_code,
        "destination": destination_code,
        "departure_at": date,
        "return_at": date,
        "unique": False,
        "sorting": "price",
        "direct": False,
        "limit": 5,
        "token": AVIASALES_TOKEN,
    }
    try:
        resp = requests.get(FLIGHT_SEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        logger.exception("Failed to fetch flights: %s", e)
        return []


def build_search_url(origin: str, destination: str, date: str) -> Optional[str]:
    """Return Aviasales search URL."""
    if not AVIASALES_TOKEN:
        logger.error("AVIASALES_TOKEN is not set")
        return None
    origin_code = search_iata(origin)
    destination_code = search_iata(destination)
    if not origin_code or not destination_code:
        return None

    dd, mm = date.split("-")[2], date.split("-")[1]
    return f"https://www.aviasales.ru/search/{origin_code}{dd}{mm}{destination_code}1"
