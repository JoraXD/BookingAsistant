import os
import importlib
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

import bookingassistant.parser as parser
importlib.reload(parser)


@pytest.mark.asyncio
async def test_generate_question_fallback_on_mismatch(monkeypatch):
    async def fake_generate_text(prompt):
        return "Куда вы планируете отправиться?"

    monkeypatch.setattr(parser, "generate_text", fake_generate_text)
    question = await parser.generate_question("from", "Не подскажете, из какого города выезжаем?")
    assert "куда" not in question.lower()
    assert question.startswith("Не подскажете")


@pytest.mark.asyncio
async def test_generate_question_fallback_on_confirmation(monkeypatch):
    async def fake_generate_text(prompt):
        return (
            "Здравствуйте! Уточните, пожалуйста, правильно ли я понимаю, что вы хотите"
            " забронировать билеты: отправление — неизвестно, прибытие — Минск, даты"
            " поездки — неизвестны, вид транспорта — неизвестен? Подтвердите, пожалуйста."
        )

    monkeypatch.setattr(parser, "generate_text", fake_generate_text)
    question = await parser.generate_question("from", "Не подскажете, из какого города выезжаем?")
    assert "подтвер" not in question.lower()
    assert question.startswith("Не подскажете")
