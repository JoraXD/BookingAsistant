import os
import pytest
from aioresponses import aioresponses

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

import bookingassistant.parser as parser


@pytest.mark.asyncio
async def test_complete_slots_marks_autofilled():
    slots = {"from": None, "to": "Минск", "date": None, "transport": "bus"}
    missing = ["from", "date"]
    response = {
        "result": {
            "alternatives": [
                {"message": {"text": '{"date": "2025-08-27"}'}}
            ]
        }
    }
    with aioresponses() as m:
        m.post(parser.API_URL, payload=response)
        result, question, auto = await parser.complete_slots(slots, missing)
    assert result["date"] == "2025-08-27"
    assert "date" in auto
    assert "from" not in auto
