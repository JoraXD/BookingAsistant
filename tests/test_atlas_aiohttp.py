import pytest
import aiohttp
from aioresponses import aioresponses
from yarl import URL

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import atlas


@pytest.mark.asyncio
async def test_search_city_id_calls_api():
    with aioresponses() as m:
        m.get(f"{atlas.CITY_URL}?term=Moscow", payload={"cities": [{"id": 42}]})
        cid = await atlas.search_city_id("Moscow")
        assert cid == 42
        assert ("GET", URL(f"{atlas.CITY_URL}?term=Moscow")) in m.requests


@pytest.mark.asyncio
async def test_link_has_routes_handles_error():
    url = atlas.build_routes_url("A", "B", "2025-01-01")
    with aioresponses() as m:
        m.get(url, exception=aiohttp.ClientError)
        ok = await atlas.link_has_routes("A", "B", "2025-01-01")
        assert ok is False
