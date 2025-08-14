import os

import aiohttp
import pytest
from aioresponses import aioresponses
from yarl import URL

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

import bookingassistant.parser as parser
from bookingassistant.parser import parse_transport
from bookingassistant.utils import display_transport


def test_plane():
    assert parse_transport("хочу полететь в Москву") == "plane"


def test_bus():
    assert parse_transport("доедем на басе в Казань") == "bus"


def test_train():
    assert parse_transport("билеты на поезд до Сочи") == "train"


def test_default():
    assert parse_transport("нужно в Нижний Новгород") is None


def test_display_transport():
    assert display_transport("plane") == "самолет"
    assert display_transport("bus") == "автобус"
    assert display_transport("train") == "поезд"
    assert display_transport(None) == "не указан"


@pytest.mark.asyncio
async def test_question_on_missing_transport():
    slots = {
        "from": "Москва",
        "to": "Казань",
        "date": "2025-08-05",
        "transport": None,
    }
    with aioresponses() as m:
        m.post(parser.API_URL, exception=aiohttp.ClientError, repeat=True)
        payload = {
            "last_question": None,
            "user_input": "",
            "known_slots": slots,
        }
        updated, question = await parser.complete_slots(payload, ["transport"])
        assert ("POST", URL(parser.API_URL)) in m.requests
    assert updated["transport"] is None
    assert question == parser.TRANSPORT_QUESTION_FALLBACK


@pytest.mark.asyncio
async def test_complete_slots_skipped_when_full():
    slots = {
        "from": "Москва",
        "to": "Казань",
        "date": "2025-08-05",
        "transport": "bus",
    }
    with aioresponses() as m:
        payload = {
            "last_question": None,
            "user_input": "",
            "known_slots": slots,
        }
        updated, question = await parser.complete_slots(payload, [])
        assert ("POST", URL(parser.API_URL)) not in m.requests
    assert updated["from"] == slots["from"]
    assert updated["to"] == slots["to"]
    assert updated["date"] == slots["date"]
    assert updated["transport"] == slots["transport"]
    assert question is None
