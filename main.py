import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

from config import TELEGRAM_BOT_TOKEN, MANAGER_BOT_TOKEN, MANAGER_CHAT_ID
from parser import (
    complete_slots,
    parse_history_request,
    generate_question,
    generate_confirmation,
    generate_fallback,
    parse_yes_no,
)
from atlas import build_routes_url, link_has_routes

from slot_editor import update_slots
from utils import display_transport
from storage import save_trip, get_last_trips, cancel_trip
from state_storage import (
    get_user_state,
    set_user_state,
    clear_user_state,
    StateStorageError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
manager_bot = Bot(token=MANAGER_BOT_TOKEN) if MANAGER_BOT_TOKEN else None

# Последнее время активности пользователя
last_seen: Dict[int, datetime] = {}

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


async def greet_if_needed(message: Message):
    uid = message.from_user.id
    now = datetime.utcnow()
    last = last_seen.get(uid)
    if not last or now - last > timedelta(hours=2):
        await message.answer(
            'Привет! Я помогу забронировать поездку. Расскажите, куда и когда хотите ехать 😄'
        )
    last_seen[uid] = now


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await greet_if_needed(message)


@dp.message(Command('help', 'info'))
async def cmd_help(message: Message):
    await greet_if_needed(message)
    await message.answer(
        'Отправьте сообщение, например: "Хочу завтра в Москву на поезде".\n'
        'Доступные команды:\n'
        '/start - начать заново\n'
        '/cancel - сбросить сессию'
    )


@dp.message(Command('cancel'))
async def cmd_cancel(message: Message):
    await greet_if_needed(message)
    try:
        await clear_user_state(message.from_user.id)
    except StateStorageError as e:
        logger.exception("Failed to clear state: %s", e)
        await message.answer('Сервис временно недоступен, попробуйте позже.')
        return
    await message.answer('Хорошо, начинаем заново. Расскажите ещё раз о поездке!')


async def handle_slots(message: Message, state: Optional[Dict[str, Optional[str]]] = None):
    text = message.text
    uid = message.from_user.id
    if state is None:
        try:
            state = await get_user_state(uid) or {}
        except StateStorageError as e:
            logger.exception("Failed to load state: %s", e)
            await message.answer('Сервис временно недоступен, попробуйте позже.')
            return
    question = state.pop('last_question', None)

    session_data = {uid: state}
    slots, changed = await update_slots(uid, text, session_data, question)

    slots, transport_question = await complete_slots(slots)

    state = session_data[uid] = slots
    try:
        await set_user_state(uid, state)
    except StateStorageError as e:
        logger.exception("Failed to save state: %s", e)
        await message.answer('Сервис временно недоступен, попробуйте позже.')
        return
    missing = get_missing_slots(slots)

    changed_msg = ''
    if changed:
        parts = [
            f"{FIELD_NAMES[k]} на {display_transport(v) if k == 'transport' else v}"
            for k, v in changed.items()
        ]
        changed_msg = 'Изменил ' + ', '.join(parts) + '.\n'

    if not changed and all(not v for v in slots.values()):
        text = await generate_fallback(message.text, DEFAULT_FALLBACK)
        await message.answer(text)
        return

    if missing:
        if transport_question and 'transport' in missing:
            question_text = transport_question
        else:
            question_text = await generate_question(missing[0], DEFAULT_QUESTIONS[missing[0]])
        state['last_question'] = question_text
        try:
            await set_user_state(uid, state)
        except StateStorageError as e:
            logger.exception("Failed to save state: %s", e)
        await message.answer(changed_msg + question_text)
    else:
        summary = await generate_confirmation(
            slots,
            f"Отлично, вот что получилось: {display_transport(slots['transport'])} {slots['from']} → {slots['to']} {slots['date']}. Всё верно?",
        )
        await message.answer(changed_msg + summary)
        state['confirm'] = True
        try:
            await set_user_state(uid, state)
        except StateStorageError as e:
            logger.exception("Failed to save state: %s", e)


@dp.message()
async def handle_message(message: Message):
    await greet_if_needed(message)
    uid = message.from_user.id
    try:
        state = await get_user_state(uid) or {}
    except StateStorageError as e:
        logger.exception("Failed to load state: %s", e)
        await message.answer('Сервис временно недоступен, попробуйте позже.')
        return
    action = await parse_history_request(message.text)

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
    if state.get('await_search'):
        choice = await parse_yes_no(message.text)
        if choice == 'yes':
            slots = dict(state)
            slots.pop('await_search', None)
            try:
                await clear_user_state(uid)
            except StateStorageError as e:
                logger.exception("Failed to clear state: %s", e)
                await message.answer('Сервис временно недоступен, попробуйте позже.')
                return
            if slots.get('transport', '').lower() in {'автобус', 'bus', 'автобусы'}:
                url = build_routes_url(slots['from'], slots['to'], slots['date'])
                if await link_has_routes(slots['from'], slots['to'], slots['date']):
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
                "message": "Отправили заявку менеджеру, скоро с вами свяжутся!",
            }
            await message.answer(
                f"\n```\n{json.dumps(response, ensure_ascii=False, indent=2)}\n```"
            )
        elif choice == 'no':
            slots = dict(state)
            slots.pop('await_search', None)
            try:
                await clear_user_state(uid)
            except StateStorageError as e:
                logger.exception("Failed to clear state: %s", e)
                await message.answer('Сервис временно недоступен, попробуйте позже.')
                return
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
                "message": "Отправили заявку менеджеру, скоро с вами свяжутся!",
            }
            await message.answer(
                f"\n```\n{json.dumps(response, ensure_ascii=False, indent=2)}\n```"
            )
        else:
            await message.answer("Напишите, пожалуйста, да или нет.")
        return

    if state.get('confirm'):
        if 'отмен' in message.text.lower():
            try:
                await clear_user_state(uid)
            except StateStorageError as e:
                logger.exception("Failed to clear state: %s", e)
                await message.answer('Сервис временно недоступен, попробуйте позже.')
                return
            await message.answer('Бронирование отменено. Если захотите, можем попробовать ещё раз!')
            return

        choice = await parse_yes_no(message.text)
        if choice == 'yes':
            state.pop('confirm', None)
            state['await_search'] = True
            try:
                await set_user_state(uid, state)
            except StateStorageError as e:
                logger.exception("Failed to save state: %s", e)
                await message.answer('Сервис временно недоступен, попробуйте позже.')
                return
            await message.answer('Хотите, я поищу билеты?')
        else:
            state.pop('confirm', None)
            session_data = {uid: state}
            slots, changed = await update_slots(uid, message.text, session_data)
            slots, transport_question = await complete_slots(slots)
            state = session_data[uid]
            changed_msg = ''
            if changed:
                parts = [
                    f"{FIELD_NAMES[k]} на {display_transport(v) if k == 'transport' else v}"
                    for k, v in changed.items()
                ]
                changed_msg = 'Изменил ' + ', '.join(parts) + '.\n'

            missing = get_missing_slots(slots)
            if missing:
                if transport_question and 'transport' in missing:
                    question_text = transport_question
                else:
                    question_text = await generate_question(missing[0], DEFAULT_QUESTIONS[missing[0]])
                state['last_question'] = question_text
                try:
                    await set_user_state(uid, state)
                except StateStorageError as e:
                    logger.exception("Failed to save state: %s", e)
                await message.answer(changed_msg + question_text)
            else:
                summary = await generate_confirmation(
                    slots,
                    f"Отлично, вот что получилось: {display_transport(slots['transport'])} {slots['from']} → {slots['to']} {slots['date']}. Всё верно?",
                )
                await message.answer(changed_msg + summary)
                state['confirm'] = True
                try:
                    await set_user_state(uid, state)
                except StateStorageError as e:
                    logger.exception("Failed to save state: %s", e)
        return

    await handle_slots(message, state)



async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
