import asyncio
import json
import logging
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from config import TELEGRAM_BOT_TOKEN, MANAGER_BOT_TOKEN, MANAGER_CHAT_ID
from parser import (
    complete_slots,
    parse_history_request,
    generate_question,
    generate_confirmation,
    generate_fallback,
)
from atlas import build_routes_url, link_has_routes

from slot_editor import update_slots
from utils import display_transport
from storage import save_trip, get_last_trips, cancel_trip

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
manager_bot = Bot(token=MANAGER_BOT_TOKEN) if MANAGER_BOT_TOKEN else None

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

# Вопросы по умолчанию, если генерация через GPT не сработала
DEFAULT_QUESTIONS = {
    'from': 'Не подскажете, из какого города выезжаем? 🙂',
    'to': 'Отлично, осталось уточнить пункт назначения 😉',
    'date': 'Хорошо, а дату поездки помните?',
    'transport': 'Какой транспорт предпочтёте: автобус, поезд или самолёт?'
}

# Ответ по умолчанию, если не удалось распознать сообщение
DEFAULT_FALLBACK = (
    'Кажется, что-то пропустил… Можете повторить, пожалуйста?'
)

# Названия слотов для сообщений об изменениях
FIELD_NAMES = {
    'from': 'город отправления',
    'to': 'город назначения',
    'date': 'дату',
    'transport': 'транспорт',
}


def get_missing_slots(slots: Dict[str, Optional[str]]):
    return [key for key, value in slots.items() if not value]


async def notify_manager(slots: Dict[str, Optional[str]], user: types.User):
    """Send booking info to manager bot if configured."""
    if not manager_bot or not MANAGER_CHAT_ID:
        return
    username = user.username or f"id{user.id}"
    text = (
        f"Новое бронирование от @{username}:\n"
        f"```\n{json.dumps(slots, ensure_ascii=False, indent=2)}\n```"
    )
    try:
        await manager_bot.send_message(int(MANAGER_CHAT_ID), text)
    except Exception as e:
        logger.exception("Failed to notify manager: %s", e)


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer('Привет! Я помогу забронировать поездку. Расскажите, куда и когда хотите ехать 😄')


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
    await message.answer('Хорошо, начинаем заново. Расскажите ещё раз о поездке!')


async def handle_slots(message: Message):
    text = message.text
    uid = message.from_user.id
    question = user_data.get(uid, {}).pop('last_question', None)

    slots, changed = update_slots(uid, text, user_data, question)

    slots = complete_slots(slots)

    user_data[uid] = slots
    missing = get_missing_slots(slots)

    changed_msg = ''
    if changed:
        parts = [
            f"{FIELD_NAMES[k]} на {display_transport(v) if k == 'transport' else v}"
            for k, v in changed.items()
        ]
        changed_msg = 'Изменил ' + ', '.join(parts) + '.\n'

    if not changed and all(not v for v in slots.values()):
        text = generate_fallback(message.text, DEFAULT_FALLBACK)
        await message.answer(text)
        return

    if missing:
        question_text = generate_question(missing[0], DEFAULT_QUESTIONS[missing[0]])
        user_data[uid]['last_question'] = question_text
        await message.answer(changed_msg + question_text)
    else:
        summary = generate_confirmation(
            slots,
            f"Отлично, вот что получилось: {display_transport(slots['transport'])} {slots['from']} → {slots['to']} {slots['date']}. Всё верно?",
        )
        await message.answer(changed_msg + summary, reply_markup=confirm_keyboard)
        user_data[uid]['confirm'] = True


@dp.message()
async def handle_message(message: Message):
    uid = message.from_user.id
    action = parse_history_request(message.text)

    if action.get('action') == 'show':
        limit = int(action.get('limit', 5))
        trips = get_last_trips(uid, limit=limit)
        if not trips:
            await message.answer('У вас нет поездок.')
        else:
            lines = [
                f"{t['id']}: {t['origin']} → {t['destination']} {t['date']} "
                f"{display_transport(t['transport'])} [{t['status']}]"
                for t in trips
            ]
            await message.answer('\n'.join(lines))
        return

    if action.get('action') == 'cancel':
        dest = action.get('destination', '').lower()
        if dest:
            trips = get_last_trips(uid, limit=20)
            for t in trips:
                if t['destination'].lower() == dest and t['status'] == 'active':
                    cancel_trip(t['id'])
                    await message.answer(
                        f"Поездка в {t['destination']} отменена."
                    )
                    return
        await message.answer('Поездка не найдена.')
        return
    if user_data.get(uid, {}).get('confirm'):
        if message.text.lower() in {'да', 'yes', 'confirm', 'подтвердить'}:
            slots = user_data.pop(uid)
            slots.pop('confirm', None)
            if slots.get('transport', '').lower() in {'автобус', 'bus', 'автобусы'}:
                url = build_routes_url(slots['from'], slots['to'], slots['date'])
                if link_has_routes(slots['from'], slots['to'], slots['date']):
                    await message.answer(url)
                else:
                    await message.answer('Рейсы не найдены.')
            await notify_manager(slots, message.from_user)
            save_trip({
                'user_id': uid,
                'origin': slots['from'],
                'destination': slots['to'],
                'date': slots['date'],
                'transport': slots['transport'],
                'status': 'active',
            })
            response = {
                "message": "Отправили заявку менеджеру, скоро с вами свяжутся!"
            }
            await message.answer(
                f"\n```\n{json.dumps(response, ensure_ascii=False, indent=2)}\n```"
            )
        elif message.text.lower() in {'отмена', 'cancel'}:
            user_data.pop(uid, None)
            await message.answer('Бронирование отменено. Если захотите, можем попробовать ещё раз!')
        else:
            # Пользователь хочет изменить слоты во время подтверждения
            user_data[uid].pop('confirm', None)
            slots, changed = update_slots(uid, message.text, user_data)
            slots = complete_slots(slots)
            changed_msg = ''
            if changed:
                parts = [
                    f"{FIELD_NAMES[k]} на {display_transport(v) if k == 'transport' else v}"
                    for k, v in changed.items()
                ]
                changed_msg = 'Изменил ' + ', '.join(parts) + '.\n'

            missing = get_missing_slots(slots)
            if missing:
                question_text = generate_question(missing[0], DEFAULT_QUESTIONS[missing[0]])
                user_data[uid]['last_question'] = question_text
                await message.answer(changed_msg + question_text)
            else:
                summary = generate_confirmation(
                    slots,
                    f"Отлично, вот что получилось: {display_transport(slots['transport'])} {slots['from']} → {slots['to']} {slots['date']}. Всё верно?",
                )
                await message.answer(
                    changed_msg + summary,
                    reply_markup=confirm_keyboard,
                )
                user_data[uid]['confirm'] = True
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
        await notify_manager(slots, query.from_user)
        save_trip({
            'user_id': uid,
            'origin': slots['from'],
            'destination': slots['to'],
            'date': slots['date'],
            'transport': slots['transport'],
            'status': 'active',
        })
        response = {
            "message": "Отправили заявку менеджеру, скоро с вами свяжутся!"
        }
        await query.message.answer(
            f"\n```\n{json.dumps(response, ensure_ascii=False, indent=2)}\n```"
        )
    await query.answer()


@dp.callback_query(F.data == 'reject')
async def cb_reject(query: types.CallbackQuery):
    user_data.pop(query.from_user.id, None)
    await query.message.edit_reply_markup()
    await query.message.answer('Бронирование отклонено. Если захотите изменить детали, просто напишите ещё раз.')
    await query.answer()


@dp.callback_query(F.data == 'cancel')
async def cb_cancel(query: types.CallbackQuery):
    user_data.pop(query.from_user.id, None)
    await query.message.edit_reply_markup()
    await query.message.answer('Бронирование отменено. Обращайтесь, если понадобится новая поездка!')
    await query.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
