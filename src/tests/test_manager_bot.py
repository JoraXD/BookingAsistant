import os
import importlib
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Message, Chat, User

os.environ["TELEGRAM_BOT_TOKEN"] = "123:abc"
os.environ["MANAGER_BOT_TOKEN"] = "456:def"

tmp = tempfile.NamedTemporaryFile(delete=False)
os.environ["TRIPS_DB"] = tmp.name
tmp.close()

import bookingassistant.config as config

importlib.reload(config)
import bookingassistant.storage as storage
import bookingassistant.manager_bot as manager_bot

importlib.reload(storage)
importlib.reload(manager_bot)

storage.init_db()


def _make_message(text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=123, is_bot=False, first_name="Test"),
        text=text,
    )


@pytest.mark.asyncio
async def test_accept_price_confirm_commands():
    storage.init_db()
    trip_id = storage.save_trip(
        {
            "user_id": 123,
            "origin": "A",
            "destination": "B",
            "date": "2025-01-01",
            "transport": "bus",
        }
    )

    msg_accept = _make_message(f"/accept {trip_id}")
    object.__setattr__(msg_accept, "answer", AsyncMock())
    manager_bot.user_bot.send_message = AsyncMock()
    await manager_bot.cmd_accept(msg_accept)
    trip = storage.get_trip(trip_id)
    assert trip["status"] == "accepted"
    manager_bot.user_bot.send_message.assert_called_with(
        123, f"Вашу заявку №{trip_id} приняли в работу"
    )

    msg_price = _make_message(f"/price {trip_id} 1000")
    object.__setattr__(msg_price, "answer", AsyncMock())
    manager_bot.user_bot.send_message = AsyncMock()
    await manager_bot.cmd_price(msg_price)
    trip = storage.get_trip(trip_id)
    assert trip["status"] == "awaiting_payment"
    manager_bot.user_bot.send_message.assert_called()

    msg_confirm = _make_message(f"/confirm {trip_id}")
    object.__setattr__(msg_confirm, "answer", AsyncMock())
    manager_bot.user_bot.send_document = AsyncMock()
    await manager_bot.cmd_confirm(msg_confirm)
    trip = storage.get_trip(trip_id)
    assert trip["status"] == "confirmed"
    manager_bot.user_bot.send_document.assert_called()


@pytest.mark.asyncio
async def test_accept_invalid_id():
    storage.init_db()
    msg = _make_message("/accept 999")
    object.__setattr__(msg, "answer", AsyncMock())
    manager_bot.user_bot.send_message = AsyncMock()

    await manager_bot.cmd_accept(msg)

    msg.answer.assert_called()
    manager_bot.user_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_list_command():
    storage.init_db()
    storage.save_trip(
        {
            "user_id": 1,
            "origin": "C",
            "destination": "D",
            "date": "2025-01-01",
            "transport": "bus",
        }
    )
    storage.save_trip(
        {
            "user_id": 1,
            "origin": "E",
            "destination": "F",
            "date": "2025-01-02",
            "transport": "bus",
            "status": "accepted",
        }
    )
    msg = _make_message("/list")
    object.__setattr__(msg, "answer", AsyncMock())

    await manager_bot.cmd_list(msg)

    msg.answer.assert_called()
    text = msg.answer.call_args[0][0]
    assert "pending" in text

    os.unlink(os.environ["TRIPS_DB"])
