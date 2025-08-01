import os
import os
import importlib
import pytest

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'x')
os.environ.setdefault('YANDEX_IAM_TOKEN', 'x')
os.environ.setdefault('YANDEX_FOLDER_ID', 'x')

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import aiohttp
from aioresponses import aioresponses
from yarl import URL

import parser
importlib.reload(parser)


@pytest.mark.asyncio
async def test_show_command():
    with aioresponses() as m:
        m.post(parser.API_URL, exception=aiohttp.ClientError)
        data = await parser.parse_history_request("покажи последние 3 поездки")
        assert ("POST", URL(parser.API_URL)) in m.requests
    assert data['action'] == 'show'
    assert data['limit'] == 3


@pytest.mark.asyncio
async def test_cancel_command():
    with aioresponses() as m:
        m.post(parser.API_URL, exception=aiohttp.ClientError)
        data = await parser.parse_history_request("пожалуйста, отмени поездку в Москву")
        assert ("POST", URL(parser.API_URL)) in m.requests
    assert data['action'] == 'cancel'
    assert data['destination'].lower() == 'москву' or data['destination'].lower() == 'москва'
