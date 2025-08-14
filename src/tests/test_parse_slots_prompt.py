import os
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

from bookingassistant import parser


@pytest.mark.asyncio
async def test_parse_slots_uses_prompt_file(monkeypatch):
    captured = {}

    async def fake_generate_text(prompt, **kwargs):
        captured["prompt"] = prompt
        return '{"from": "", "to": "", "date": "", "transport": "", "confidence": {"from": 0.0, "to": 0.0, "date": 0.0, "transport": 0.0}}'

    monkeypatch.setattr(parser, "generate_text", fake_generate_text)
    await parser.parse_slots("пример")

    with open(os.path.join(os.path.dirname(parser.__file__), "prompts", "parse_slots.txt"), encoding="utf-8") as f:
        content = f.read().strip()
    assert captured["prompt"].startswith(content)
