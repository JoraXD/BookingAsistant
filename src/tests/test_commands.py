import os
import importlib
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

import aiohttp
from aioresponses import aioresponses
from yarl import URL

import bookingassistant.parser as parser

importlib.reload(parser)

from bookingassistant.slot_editor import update_slots


@pytest.mark.asyncio
async def test_show_command():
    with aioresponses() as m:
        m.post(parser.API_URL, exception=aiohttp.ClientError)
        data = await parser.parse_history_request("покажи последние 3 поездки")
        assert ("POST", URL(parser.API_URL)) in m.requests
    assert data["action"] == "show"
    assert data["limit"] == 3


@pytest.mark.asyncio
async def test_cancel_command():
    with aioresponses() as m:
        m.post(parser.API_URL, exception=aiohttp.ClientError)
        data = await parser.parse_history_request("пожалуйста, отмени поездку в Москву")
        assert ("POST", URL(parser.API_URL)) in m.requests
    assert data["action"] == "cancel"
    assert (
        data["destination"].lower() == "москву"
        or data["destination"].lower() == "москва"
    )


@pytest.mark.asyncio
async def test_no_llm_called(monkeypatch):
    async def fake_generate_text(*args, **kwargs):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(parser, "generate_text", fake_generate_text)

    session_data = {}
    slots, changed, used_llm = await update_slots(
        1, "Я завтра в Минск на автобусе из Гродно", session_data
    )

    assert not used_llm
    assert slots["from"].lower() == "гродно"
    assert slots["to"].lower() == "минск"
    assert slots["transport"] == "bus"
    assert slots["date"]
