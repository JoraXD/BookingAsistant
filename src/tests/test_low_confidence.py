import os
import asyncio

os.environ.setdefault(
    "TELEGRAM_BOT_TOKEN", "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")
os.environ.setdefault("YANDEX_API_KEY", "x")

import bookingassistant.main as main


def test_low_confidence_triggers_question(monkeypatch):
    async def fake_generate_question(slot, fallback):
        return f"ask {slot}"

    async def fake_update_slots(uid, text, session_data, question, pre_slots=None):
        slots = {
            "from": "A",
            "to": "B",
            "date": "2024-01-01",
            "transport": "bus",
            "confidence": {"from": 0.4, "to": 0.9, "date": 0.9, "transport": 0.9},
        }
        session_data[uid] = slots
        return slots, {}

    async def fake_complete_slots(*args, **kwargs):
        raise AssertionError("complete_slots should not be called")

    async def fake_set_user_state(uid, state):
        pass

    monkeypatch.setattr(main, "generate_question", fake_generate_question)
    monkeypatch.setattr(main, "update_slots", fake_update_slots)
    monkeypatch.setattr(main, "complete_slots", fake_complete_slots)
    monkeypatch.setattr(main, "set_user_state", fake_set_user_state)

    class DummyUser:
        id = 1

    class DummyMessage:
        text = "hello"
        from_user = DummyUser()

        def __init__(self):
            self.sent = []

        async def answer(self, text):
            self.sent.append(text)

    async def scenario():
        msg = DummyMessage()
        state = {}
        await main.handle_slots(msg, state)
        return state, msg

    state, msg = asyncio.run(scenario())

    assert msg.sent == ["ask from"]
