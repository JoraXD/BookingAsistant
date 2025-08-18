import os
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")
os.environ.setdefault("YANDEX_API_KEY", "x")

from bookingassistant import parser


@pytest.mark.asyncio
async def test_parse_slots_handles_null_confidence(monkeypatch):
    async def fake_generate_text(*args, **kwargs):
        return (
            '{"from": "Елабуга", "to": "Питер", "date": "", "transport": "",'
            ' "confidence": {"from": 1, "to": null, "date": null, "transport": null}}'
        )

    monkeypatch.setattr(parser, "generate_text", fake_generate_text)
    result = await parser.parse_slots("text")
    assert result["from"] == "Елабуга"
    assert result["to"] == "Питер"
    assert result["confidence"] == {
        "from": 1.0,
        "to": 0.0,
        "date": 0.0,
        "transport": 0.0,
    }
