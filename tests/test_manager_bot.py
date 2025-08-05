import os
import importlib
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Message, Chat, User
import sys

os.environ['TELEGRAM_BOT_TOKEN'] = '123:abc'
os.environ['MANAGER_BOT_TOKEN'] = '456:def'


tmp = tempfile.NamedTemporaryFile(delete=False)
os.environ['TRIPS_DB'] = tmp.name
tmp.close()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config
importlib.reload(config)
import storage
import manager_bot
importlib.reload(storage)
importlib.reload(manager_bot)

storage.init_db()


def _make_message(text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type='private'),
        from_user=User(id=123, is_bot=False, first_name='Test'),
        text=text,
    )


@pytest.mark.asyncio
async def test_approve_command():
    storage.init_db()
    trip_id = storage.save_trip({'user_id': 123, 'origin': 'A', 'destination': 'B', 'date': '2025-01-01', 'transport': 'bus'})
    msg = _make_message(f'/approve {trip_id}')
    object.__setattr__(msg, 'answer', AsyncMock())
    manager_bot.user_bot.send_message = AsyncMock()

    await manager_bot.cmd_approve(msg)

    trip = storage.get_trip(trip_id)
    assert trip['status'] == 'approved'
    manager_bot.user_bot.send_message.assert_called_with(123, f'Вашу заявку №{trip_id} одобрили')


@pytest.mark.asyncio
async def test_approve_invalid_id():
    storage.init_db()
    msg = _make_message('/approve 999')
    object.__setattr__(msg, 'answer', AsyncMock())
    manager_bot.user_bot.send_message = AsyncMock()

    await manager_bot.cmd_approve(msg)

    msg.answer.assert_called()
    manager_bot.user_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_list_command():
    storage.init_db()
    storage.save_trip({'user_id': 1, 'origin': 'C', 'destination': 'D', 'date': '2025-01-01', 'transport': 'bus'})
    storage.save_trip({'user_id': 1, 'origin': 'E', 'destination': 'F', 'date': '2025-01-02', 'transport': 'bus', 'status': 'approved'})
    msg = _make_message('/list')
    object.__setattr__(msg, 'answer', AsyncMock())

    await manager_bot.cmd_list(msg)

    msg.answer.assert_called()
    text = msg.answer.call_args[0][0]
    assert 'pending' in text

    os.unlink(os.environ['TRIPS_DB'])
