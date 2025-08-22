import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Message, Chat, User

os.environ["TELEGRAM_BOT_TOKEN"] = "123:abc"
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

import importlib
import bookingassistant.config as config

importlib.reload(config)
import bookingassistant.main as main


def _make_message(text: str = "hi") -> Message:
    return Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=123, is_bot=False, first_name="Test"),
        text=text,
    )


@pytest.mark.asyncio
async def test_greet_once_per_day():
    msg = _make_message()
    object.__setattr__(msg, "answer", AsyncMock())
    main.last_seen.clear()

    await main.greet_if_needed(msg)
    msg.answer.assert_called_once()

    msg.answer.reset_mock()
    await main.greet_if_needed(msg)
    msg.answer.assert_not_called()

    main.last_seen[msg.from_user.id] = datetime.now(timezone.utc) - timedelta(days=1)
    msg.answer.reset_mock()
    await main.greet_if_needed(msg)
    msg.answer.assert_called_once()
