import asyncio
import json
import logging
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from config import TELEGRAM_BOT_TOKEN
from parser import parse_slots, complete_slots
from atlas import build_routes_url, link_has_routes

from utils import normalize_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Кнопки подтверждения/отмены
confirm_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='Подтвердить', callback_data='confirm'),
            InlineKeyboardButton(text='Отклонить', callback_data='reject'),
        ],
        [InlineKeyboardButton(text='Отмена', callback_data='cancel')],
    ]
)

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
    question = user_data.get(uid, {}).pop('last_question', None)

    # сначала пытаемся вытащить дату напрямую из текста пользователя
    user_date = normalize_date(text)

    parsed = parse_slots(text, question)

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
        user_data[uid]['last_question'] = question_text
        await message.answer(question_text)
    else:
        summary = (
            f"Подтвердите поездку из {slots['from']} в {slots['to']} "
            f"{slots['date']} на {slots['transport']}"
        )
        await message.answer(summary, reply_markup=confirm_keyboard)
        user_data[uid]['confirm'] = True


@dp.message()
async def handle_message(message: Message):
    uid = message.from_user.id
    if user_data.get(uid, {}).get('confirm'):
        if message.text.lower() in {'да', 'yes', 'confirm', 'подтвердить'}:
            slots = user_data.pop(uid)
            slots.pop('confirm', None)
            if slots.get('transport', '').lower() in {'автобус', 'bus', 'автобусы'}:
                url = build_routes_url(slots['from'], slots['to'], slots['date'])
                if link_has_routes(slots['from'], slots['to'], slots['date']):

                else:
                    await message.answer('Рейсы не найдены.')
            await message.answer(
                f"\n```\n{json.dumps(slots, ensure_ascii=False, indent=2)}\n```"
            )
        elif message.text.lower() in {'отмена', 'cancel'}:
            user_data.pop(uid, None)
            await message.answer('Бронирование отменено. Начните заново.')
        else:
            user_data.pop(uid, None)
            await message.answer('Бронирование отклонено. Начните заново.')
    else:
        await handle_slots(message)


@dp.callback_query(F.data == 'confirm')
async def cb_confirm(query: types.CallbackQuery):
    uid = query.from_user.id
    slots = user_data.pop(uid, None)
    await query.message.edit_reply_markup()
    if slots:
        slots.pop('confirm', None)
        if slots.get('transport', '').lower() in {'автобус', 'bus', 'автобусы'}:
            url = build_routes_url(slots['from'], slots['to'], slots['date'])
            if link_has_routes(slots['from'], slots['to'], slots['date']):
                await query.message.answer(url)

            else:
                await query.message.answer('Рейсы не найдены.')
        await query.message.answer(
            f"\n```\n{json.dumps(slots, ensure_ascii=False, indent=2)}\n```"
        )
    await query.answer()


@dp.callback_query(F.data == 'reject')
async def cb_reject(query: types.CallbackQuery):
    user_data.pop(query.from_user.id, None)
    await query.message.edit_reply_markup()
    await query.message.answer('Бронирование отклонено. Начните заново.')
    await query.answer()


@dp.callback_query(F.data == 'cancel')
async def cb_cancel(query: types.CallbackQuery):
    user_data.pop(query.from_user.id, None)
    await query.message.edit_reply_markup()
    await query.message.answer('Бронирование отменено. Начните заново.')
    await query.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
