import logging
from typing import List, Dict, Optional

import requests

SEARCH_URL = "https://atlasbus.ru/api/rasp/v3/routes/search"
CITY_URL = "https://atlasbus.ru/api/geo/v1/cities/search"


def search_city_id(name: str) -> Optional[int]:
    """Return first matching city id."""
    params = {"term": name}
    try:
        resp = requests.get(CITY_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        cities = data.get("cities") or data.get("items")
        if cities:
            return cities[0].get("id")
    except Exception as e:
        logging.exception("Failed to fetch city id: %s", e)
    return None



def search_buses(origin: str, destination: str, date: str) -> List[Dict]:
    """Return list of bus routes from atlasbus.ru."""
    origin_id = search_city_id(origin)
    destination_id = search_city_id(destination)
    if origin_id is None or destination_id is None:
        logging.error("Unknown city: %s -> %s", origin, destination)
        return []

    params = {
        "fromCity": origin_id,
        "toCity": destination_id,

        "date": date,
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("routes") or data.get("items") or []

    except Exception as e:
        logging.exception("Failed to fetch buses: %s", e)
        return []
