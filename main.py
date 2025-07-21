import asyncio
import json
import logging
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

from config import TELEGRAM_BOT_TOKEN
from parser import parse_slots, complete_slots
from utils import normalize_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Сохранение слотов по user_id
user_data: Dict[int, Dict[str, Optional[str]]] = {}


def get_missing_slots(slots: Dict[str, Optional[str]]):
    return [key for key, value in slots.items() if not value]


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer('Привет! Я помогу забронировать поездку. Опишите её в свободной форме.')


@dp.message(Command('help', 'info'))
async def cmd_help(message: Message):
    await message.answer(
        'Отправьте сообщение, например: "Хочу завтра в Москву на поезде".\n'
        'Доступные команды:\n'
        '/start - начать заново\n'
        '/cancel - сбросить сессию'
    )


@dp.message(Command('cancel'))
async def cmd_cancel(message: Message):
    user_data.pop(message.from_user.id, None)
    await message.answer('Сессия сброшена. Опишите новую поездку.')


async def handle_slots(message: Message):
    text = message.text
    uid = message.from_user.id
    slots = user_data.get(uid, {'from': None, 'to': None, 'date': None, 'transport': None})

    # сначала пытаемся вытащить дату напрямую из текста пользователя
    user_date = normalize_date(text)

    parsed = parse_slots(text)

    if user_date:
        parsed['date'] = user_date
    elif parsed.get('date'):
        # нормализуем дату, возвращённую YandexGPT
        parsed['date'] = normalize_date(parsed['date']) or parsed['date']

    # обновляем слоты
    for key in ['from', 'to', 'date', 'transport']:
        value = parsed.get(key)
        if value:
            slots[key] = value

    # отправляем уже известные данные для дополнения
    slots = complete_slots(slots)

    user_data[uid] = slots
    missing = get_missing_slots(slots)

    if missing:
        questions = {
            'from': 'Из какого города вы отправляетесь?',
            'to': 'В какой город хотите отправиться?',
            'date': 'На какую дату планируете поездку?',
            'transport': 'Какой транспорт предпочитаете: автобус, поезд или самолет?'
        }
        question_text = questions[missing[0]]
        await message.answer(question_text)
    else:
        summary = (
            f"Подтвердите поездку из {slots['from']} в {slots['to']} "
            f"{slots['date']} на {slots['transport']}. (да/нет)"
        )
        await message.answer(summary)
        user_data[uid]['confirm'] = True


@dp.message()
async def handle_message(message: Message):
    uid = message.from_user.id
    if user_data.get(uid, {}).get('confirm'):
        if message.text.lower() in {'да', 'yes', 'confirm', 'подтвердить'}:
            slots = user_data.pop(uid)
            slots.pop('confirm', None)
            await message.answer(f'\n```\n{json.dumps(slots, ensure_ascii=False, indent=2)}\n```')
        else:
            user_data.pop(uid, None)
            await message.answer('Бронирование отменено. Начните заново.')
    else:
        await handle_slots(message)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
