import os
import pytest
from datetime import datetime, timedelta

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

from bookingassistant.utils import pre_extract_slots


def test_pre_extract_slots_basic():
    text = "Я завтра в Минск на автобусе из Гродно"
    slots = pre_extract_slots(text)
    assert slots["from"].lower() == "гродно"
    assert slots["to"].lower() == "минск"
    assert slots["transport"] == "bus"
    expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert slots["date"] == expected
