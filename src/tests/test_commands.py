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
import bookingassistant.slot_editor as slot_editor
from bookingassistant.utils import pre_extract_slots

importlib.reload(parser)


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
    called = False

    async def fake_generate_text(*args, **kwargs):
        nonlocal called
        called = True
        return ""

    monkeypatch.setattr(parser, "generate_text", fake_generate_text)

    async def fake_parse_slots(*args, **kwargs):
        raise AssertionError("parse_slots should not be called")

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    session_data = {}
    text = "Я завтра в Минск на автобусе из Гродно"
    pre = pre_extract_slots(text)
    await slot_editor.update_slots(1, text, session_data, pre_slots=pre)

    assert called is False
