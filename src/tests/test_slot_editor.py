import os
import pytest

# Prevent config module from raising missing environment errors during import
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("YANDEX_IAM_TOKEN", "test")
os.environ.setdefault("YANDEX_FOLDER_ID", "test")

from bookingassistant import slot_editor


@pytest.mark.asyncio
async def test_update_slots_ignores_hallucinations(monkeypatch):
    session = {42: {"from": None, "to": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {
            "from": "Москва",
            "to": "Санкт-Петербург",
            "date": "2025-01-01",
            "transport": "plane",
        }

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(42, "просто болтаю", session)

    assert slots == {"from": None, "to": None, "date": None, "transport": None}
    assert changed == {}


@pytest.mark.asyncio
async def test_update_slots_accepts_city_abbreviation(monkeypatch):
    session = {1: {"from": None, "to": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {"from": None, "to": "Москва", "date": None, "transport": None}

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(1, "еду в мск", session)

    assert slots["to"] == "Москва"
    assert changed == {}
