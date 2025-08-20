import os

import pytest
from aioresponses import aioresponses

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

from bookingassistant.utils import normalize_time
from bookingassistant.parser import API_URL


@pytest.mark.asyncio
async def test_normalize_time_digits():
    with aioresponses() as m:
        m.post(
            API_URL,
            payload={"result": {"alternatives": [{"message": {"text": "09:30"}}]}},
        )
        assert await normalize_time("9:30") == "09:30"


@pytest.mark.asyncio
async def test_normalize_time_text():
    with aioresponses() as m:
        m.post(
            API_URL,
            payload={"result": {"alternatives": [{"message": {"text": "20:00"}}]}},
        )
        assert await normalize_time("в восемь вечера") == "20:00"
