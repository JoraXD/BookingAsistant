import logging
from typing import List, Dict
import requests

SEARCH_URL = "https://atlasbus.ru/api/rasp/v3/routes/search"


def search_buses(origin: str, destination: str, date: str) -> List[Dict]:
    """Return list of bus routes from atlasbus.ru."""
    params = {
        "fromCity": origin,
        "toCity": destination,
        "date": date,
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("routes", [])
    except Exception as e:
        logging.exception("Failed to fetch buses: %s", e)
        return []
