import os
import pytest

os.environ.setdefault(
    "TELEGRAM_BOT_TOKEN", "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

from bookingassistant import main, parser, slot_editor


@pytest.mark.asyncio
async def test_unknown_city_triggers_question(monkeypatch):
    async def fake_parse_slots(message, question=None):
        return {
            "from": "Неверск",
            "to": "Москва",
            "date": "2025-08-05",
            "transport": "train",
            "confidence": {"from": 0.9, "to": 0.9, "date": 0.9, "transport": 0.9},
        }

    async def fake_complete_slots(payload, missing):
        return payload["known_slots"], None

    async def fake_generate_question(slot, fallback):
        return f"ask {slot}"

    async def fake_set_user_state(uid, state):
        pass

    monkeypatch.setattr(slot_editor, "parse_slots", fake_parse_slots)
    monkeypatch.setattr(parser, "complete_slots", fake_complete_slots)
    monkeypatch.setattr(main, "generate_question", fake_generate_question)
    monkeypatch.setattr(main, "set_user_state", fake_set_user_state)

    class DummyUser:
        id = 1

    class DummyMessage:
        text = "еду в Москву"
        from_user = DummyUser()

        def __init__(self):
            self.sent = []

        async def answer(self, text):
            self.sent.append(text)

    msg = DummyMessage()
    state = {}
    await main.handle_slots(msg, state)
    assert msg.sent == ["ask from"]
