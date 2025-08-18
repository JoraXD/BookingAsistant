import os
import json
import re
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")
os.environ.setdefault("YANDEX_API_KEY", "x")

from bookingassistant import parser


@pytest.mark.asyncio
async def test_complete_slots_prompt_limited_fields(monkeypatch):
    captured = {}

    async def fake_generate_text(prompt, **kwargs):
        if "prompt" not in captured:
            captured["prompt"] = prompt
        return '{"from": "", "to": "", "date": "", "transport": "bus", "confidence": {"from": 1.0, "to": 1.0, "date": 1.0, "transport": 1.0}}'

    monkeypatch.setattr(parser, "generate_text", fake_generate_text)

    payload = {
        "last_question": "Откуда вы едете?",
        "user_input": "Из Москвы",
        "known_slots": {
            "from": None,
            "to": "Казань",
            "date": "2025-08-05",
            "transport": None,
        },
    }

    await parser.complete_slots(payload, ["from", "transport"])

    match = re.search(r"\{.*\}", captured["prompt"], re.DOTALL)
    data = json.loads(match.group(0))
    assert set(data.keys()) == {"last_question", "user_input", "known_slots"}
    assert data["user_input"] == "Из Москвы"
    assert data["known_slots"]["to"] == "Казань"
