import os
import pytest
from aioresponses import aioresponses
from yarl import URL

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")
os.environ.setdefault("YANDEX_API_KEY", "x")

from bookingassistant.parser import parse_slots
from bookingassistant.gpt import API_URL
from bookingassistant.models import SlotsModel


@pytest.mark.asyncio
async def test_parse_slots_retry_success():
    bad = {"result": {"alternatives": [{"message": {"text": "не json"}}]}}
    good_text = (
        "{\"from\": \"A\", \"to\": \"B\", \"date\": \"2024-01-01\", \"transport\": \"bus\", \"confidence\": {\"from\": 0.5, \"to\": 0.6, \"date\": 0.7, \"transport\": 0.8}}"
    )
    good = {"result": {"alternatives": [{"message": {"text": good_text}}]}}
    with aioresponses() as m:
        m.post(API_URL, payload=bad)
        m.post(API_URL, payload=good)
        result = await parse_slots("text")
        assert result == {
            "from": "A",
            "to": "B",
            "date": "2024-01-01",
            "transport": "bus",
            "confidence": {"from": 0.5, "to": 0.6, "date": 0.7, "transport": 0.8},
        }
        assert len(m.requests[('POST', URL(API_URL))]) == 2


@pytest.mark.asyncio
async def test_parse_slots_retry_default():
    bad = {"result": {"alternatives": [{"message": {"text": "не json"}}]}}
    with aioresponses() as m:
        m.post(API_URL, payload=bad)
        m.post(API_URL, payload=bad)
        result = await parse_slots("text")
        expected = SlotsModel().model_dump(by_alias=True)
        assert result == expected
        assert len(m.requests[('POST', URL(API_URL))]) == 2
