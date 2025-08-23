import os
import pytest

# Prevent config module from raising missing environment errors during import
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("YANDEX_IAM_TOKEN", "test")
os.environ.setdefault("YANDEX_FOLDER_ID", "test")

from bookingassistant import slot_editor


@pytest.mark.asyncio
async def test_update_slots_ignores_hallucinations(monkeypatch):
    session = {42: {"origin": None, "destination": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {
            "origin": "Москва",
            "destination": "Санкт-Петербург",
            "date": "2025-01-01",
            "transport": "plane",
        }

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(42, "просто болтаю", session)

    assert slots == {"origin": None, "destination": None, "date": None, "transport": None}
    assert changed == {}


@pytest.mark.asyncio
async def test_update_slots_accepts_city_abbreviation(monkeypatch):
    session = {1: {"origin": None, "destination": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {"origin": None, "destination": "Москва", "date": None, "transport": None}

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(1, "еду в мск", session)

    assert slots["destination"] == "Москва"
    assert changed == {}


@pytest.mark.asyncio
async def test_update_slots_reassigns_city_on_mismatch(monkeypatch):
    session = {1: {"origin": None, "destination": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {"origin": "Москва", "destination": None, "date": None, "transport": None}

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(1, "в мск", session)

    assert slots == {
        "origin": None,
        "destination": "Москва",
        "date": None,
        "transport": None,
    }
    assert changed == {}


@pytest.mark.asyncio
async def test_update_slots_preserves_parsed_date(monkeypatch):
    session = {1: {"origin": None, "destination": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {"origin": "Москва", "destination": "Москва", "date": "2025-01-01", "transport": None}

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(1, "В москву завтра", session)

    assert slots == {
        "origin": None,
        "destination": "Москва",
        "date": "2025-01-01",
        "transport": None,
    }
    assert changed == {}


@pytest.mark.asyncio
async def test_update_slots_drops_hallucinated_date(monkeypatch):
    session = {1: {"origin": None, "destination": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {"origin": None, "destination": "Москва", "date": "2025-01-01", "transport": None}

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, _ = await slot_editor.update_slots(1, "в москву", session)

    assert slots["date"] is None


@pytest.mark.asyncio
async def test_update_slots_converts_placeholder_strings(monkeypatch):
    session = {1: {"origin": "Питер", "destination": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {
            "origin": "пусто",
            "destination": "Москва",
            "date": "none",
            "transport": "",
        }

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(1, "в москву", session)

    assert slots == {
        "origin": "Питер",
        "destination": "Москва",
        "date": None,
        "transport": None,
    }
    assert changed == {}


@pytest.mark.asyncio
async def test_update_slots_respects_question_context_for_origin(monkeypatch):
    session = {1: {"origin": None, "destination": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {"origin": None, "destination": "Казань", "date": None, "transport": None}

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(
        1, "Казань", session, "Из какого города вы хотите отправиться?"
    )

    assert slots == {"origin": "Казань", "destination": None, "date": None, "transport": None}
    assert changed == {}


@pytest.mark.asyncio
async def test_update_slots_respects_question_context_for_destination(monkeypatch):
    session = {1: {"origin": None, "destination": None, "date": None, "transport": None}}

    async def fake_parse_slots(message: str, question: str | None = None):
        return {"origin": "Казань", "destination": None, "date": None, "transport": None}

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)

    slots, changed = await slot_editor.update_slots(
        1, "Казань", session, "Куда планируете поехать?"
    )

    assert slots == {"origin": None, "destination": "Казань", "date": None, "transport": None}
    assert changed == {}
