import asyncio
import logging
import ssl
from typing import Dict, List, Optional

import aiohttp
import certifi

SEARCH_URL = "https://atlasbus.ru/api/rasp/v3/routes/search"
CITY_URL = "https://atlasbus.ru/api/geo/v1/cities/search"

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT))


async def search_city_id(name: str) -> Optional[int]:
    """Return first matching city id."""
    params = {"term": name}
    try:
        async with _session() as session:
            async with session.get(CITY_URL, params=params, timeout=30) as resp:
                resp.raise_for_status()
                data = await resp.json()
                cities = data.get("cities") or data.get("items")
                if cities:
                    return cities[0].get("id")
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logging.exception("Failed to fetch city id: %s", e)
    except Exception as e:
        logging.exception("Failed to fetch city id: %s", e)
    return None



async def search_buses(origin: str, destination: str, date: str) -> List[Dict]:
    """Return list of bus routes from atlasbus.ru."""
    origin_id = await search_city_id(origin)
    destination_id = await search_city_id(destination)
    if origin_id is None or destination_id is None:
        logging.error("Unknown city: %s -> %s", origin, destination)
        return []

    params = {
        "fromCity": origin_id,
        "toCity": destination_id,

        "date": date,
    }
    try:
        async with _session() as session:
            async with session.get(SEARCH_URL, params=params, timeout=30) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("routes") or data.get("items") or []
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logging.exception("Failed to fetch buses: %s", e)
    except Exception as e:
        logging.exception("Failed to fetch buses: %s", e)
    return []


def build_routes_url(origin: str, destination: str, date: str) -> str:
    """Return URL to atlasbus with pre-filled route search."""
    return f"https://atlasbus.ru/Маршруты/{origin}/{destination}?date={date}"


async def link_has_routes(origin: str, destination: str, date: str) -> bool:
    """Return True if atlasbus page for given parameters is not 404."""
    url = build_routes_url(origin, destination, date)
    try:
        async with _session() as session:
            async with session.get(url, allow_redirects=True, timeout=30) as resp:
                return resp.status != 404
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logging.exception("Failed to check routes url: %s", e)
    except Exception as e:
        logging.exception("Failed to check routes url: %s", e)
    return False
