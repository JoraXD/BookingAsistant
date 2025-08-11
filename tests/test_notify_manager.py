import os
import sys
import importlib
from unittest.mock import AsyncMock

import pytest
from aiogram.types import User

os.environ['TELEGRAM_BOT_TOKEN'] = '123:abc'
os.environ['MANAGER_BOT_TOKEN'] = '456:def'
os.environ['MANAGER_CHAT_ID'] = '789'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
importlib.reload(config)
import main
importlib.reload(main)

@pytest.mark.asyncio
async def test_notify_manager_includes_id():
    main.manager_bot.send_message = AsyncMock()
    user = User(id=1, is_bot=False, first_name='Test', username='tester')
    slots = {'from': 'A', 'to': 'B', 'date': '2025-01-01', 'transport': 'bus', 'time': '08:00'}
    await main.notify_manager(42, slots, user)
    assert main.manager_bot.send_message.called
    text = main.manager_bot.send_message.call_args[0][1]
    assert '42' in text
    assert '08:00' in text
