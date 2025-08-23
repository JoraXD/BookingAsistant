"""Основной Telegram-бот для оформления и управления поездками."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

from .config import TELEGRAM_BOT_TOKEN, MANAGER_BOT_TOKEN, MANAGER_CHAT_ID
from .texts import (
    DEFAULT_QUESTIONS,
    EXTRA_QUESTIONS,
    DEFAULT_FALLBACK,
    FIELD_NAMES,
    GREETING_MESSAGE,
    HELP_MESSAGE,
    CANCEL_MESSAGE,
    SERVICE_ERROR_MESSAGE,
    NO_TRIPS_MESSAGE,
    TRIP_CANCELLED_TEMPLATE,
    TRIP_NOT_FOUND_MESSAGE,
    ASK_SEARCH_MESSAGE,
    YESNO_PROMPT_USER,
    BOOKING_CANCELLED_MESSAGE,
    ROUTES_NOT_FOUND_MESSAGE,
    REQUEST_SENT_MESSAGE,
)
from .parser import (
    parse_history_request,
    generate_question,
    generate_confirmation,
    generate_fallback,
    parse_yes_no,
)
from .atlas import build_routes_url, link_has_routes

from .slot_editor import update_slots
from .utils import display_transport, normalize_time
from .storage import save_trip, get_last_trips, cancel_trip
from .state_storage import (
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


# Слоты, необходимые для первоначального запроса
REQUIRED_SLOTS = ["origin", "destination", "date", "transport"]


def get_missing_slots(slots: Dict[str, Optional[str]]):
    return [key for key in REQUIRED_SLOTS if not slots.get(key)]


async def notify_manager(
    trip_id: int, slots: Dict[str, Optional[str]], user: types.User
):
    """Send booking info to manager bot if configured."""
    if not manager_bot or not MANAGER_CHAT_ID:
        return
    username = user.username or f"id{user.id}"
    payload = {"id": trip_id, "user": f"@{username}", **slots}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        await manager_bot.send_message(int(MANAGER_CHAT_ID), text)
    except Exception as e:
        logger.exception("Failed to notify manager: %s", e)


async def greet_if_needed(message: Message):
    uid = message.from_user.id
    now = datetime.now(timezone.utc)
    last = last_seen.get(uid)
    # Приветствуем пользователя только один раз в сутки
    if not last or now.date() != last.date():
        await message.answer(GREETING_MESSAGE)
    last_seen[uid] = now


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await greet_if_needed(message)


@dp.message(Command("help", "info"))
async def cmd_help(message: Message):
    await greet_if_needed(message)
    await message.answer(HELP_MESSAGE)


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message):
    await greet_if_needed(message)
    try:
        await clear_user_state(message.from_user.id)
    except StateStorageError as e:
        logger.exception("Failed to clear state: %s", e)
        await message.answer(SERVICE_ERROR_MESSAGE)
        return
    await message.answer(CANCEL_MESSAGE)


async def handle_slots(
    message: Message, state: Optional[Dict[str, Optional[str]]] = None
):
    text = message.text
    uid = message.from_user.id
    if state is None:
        try:
            state = await get_user_state(uid) or {}
        except StateStorageError as e:
            logger.exception("Failed to load state: %s", e)
            await message.answer(SERVICE_ERROR_MESSAGE)
            return
    question = state.pop("last_question", None)

    session_data = {uid: state}
    slots, changed = await update_slots(uid, text, session_data, question)

    state = session_data[uid] = slots
    try:
        await set_user_state(uid, state)
    except StateStorageError as e:
        logger.exception("Failed to save state: %s", e)
        await message.answer(SERVICE_ERROR_MESSAGE)
        return
    missing = get_missing_slots(slots)

    changed_msg = ""
    if changed:
        parts = [
            f"{FIELD_NAMES[k]} на {display_transport(v) if k == 'transport' else v}"
            for k, v in changed.items()
        ]
        changed_msg = "Изменил " + ", ".join(parts) + ".\n"

    if not changed and all(not v for v in slots.values()):
        text = await generate_fallback(message.text, DEFAULT_FALLBACK)
        await message.answer(text)
        return

    if missing:
        question_text = await generate_question(
            missing[0], DEFAULT_QUESTIONS[missing[0]]
        )
        state["last_question"] = question_text
        try:
            await set_user_state(uid, state)
        except StateStorageError as e:
            logger.exception("Failed to save state: %s", e)
        await message.answer(changed_msg + question_text)
    else:
        summary = await generate_confirmation(
            slots,
            f"Отлично, вот что получилось: {display_transport(slots['transport'])} {slots['origin']} → {slots['destination']} {slots['date']}. Всё верно?",
        )
        await message.answer(changed_msg + summary)
        state["confirm"] = True
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
        await message.answer(SERVICE_ERROR_MESSAGE)
        return
    action = await parse_history_request(message.text)

    if action.get("action") == "show":
        limit = int(action.get("limit", 5))
        trips = get_last_trips(uid, limit=limit)
        if not trips:
            await message.answer(NO_TRIPS_MESSAGE)
        else:
            lines = [
                f"{t['id']}: {t['origin']} → {t['destination']} {t['date']} "
                f"{display_transport(t['transport'])} [{t['status']}]"
                for t in trips
            ]
            await message.answer("\n".join(lines))
        return

    if action.get("action") == "cancel":
        dest = action.get("destination", "").lower()
        if dest:
            trips = get_last_trips(uid, limit=20)
            for t in trips:
                if t["destination"].lower() == dest and t["status"] == "active":
                    cancel_trip(t["id"])
                    await message.answer(
                        TRIP_CANCELLED_TEMPLATE.format(destination=t["destination"])
                    )
                    return
        await message.answer(TRIP_NOT_FOUND_MESSAGE)
        return
    if state.get("extra_questions"):
        questions = state["extra_questions"]
        key = questions.pop(0)
        answer = message.text
        if key == "time":
            parsed = await normalize_time(answer)
            state[key] = parsed if parsed else answer
        else:
            state[key] = answer
        try:
            await set_user_state(uid, state)
        except StateStorageError as e:
            logger.exception("Failed to save state: %s", e)
            await message.answer(SERVICE_ERROR_MESSAGE)
            return
        if questions:
            next_key = questions[0]
            await message.answer(EXTRA_QUESTIONS[next_key])
        else:
            state.pop("extra_questions", None)
            state["await_search"] = True
            try:
                await set_user_state(uid, state)
            except StateStorageError as e:
                logger.exception("Failed to save state: %s", e)
                await message.answer(SERVICE_ERROR_MESSAGE)
                return
            await message.answer(ASK_SEARCH_MESSAGE)
        return
    if state.get("await_search"):
        choice = await parse_yes_no(message.text)
        if choice == "yes":
            slots = dict(state)
            slots.pop("await_search", None)
            try:
                await clear_user_state(uid)
            except StateStorageError as e:
                logger.exception("Failed to clear state: %s", e)
                await message.answer(SERVICE_ERROR_MESSAGE)
                return
            if slots.get("transport", "").lower() in {"автобус", "bus", "автобусы"}:
                url = build_routes_url(slots["origin"], slots["destination"], slots["date"])
                if await link_has_routes(slots["origin"], slots["destination"], slots["date"]):
                    await message.answer(url)
                else:
                    await message.answer(ROUTES_NOT_FOUND_MESSAGE)
            trip_id = save_trip(
                {
                    "user_id": uid,
                    "origin": slots["origin"],
                    "destination": slots["destination"],
                    "date": slots["date"],
                    "transport": slots["transport"],
                    "status": "pending",
                }
            )
            await notify_manager(trip_id, slots, message.from_user)
            await message.answer(
                REQUEST_SENT_MESSAGE
            )
        elif choice == "no":
            slots = dict(state)
            slots.pop("await_search", None)
            try:
                await clear_user_state(uid)
            except StateStorageError as e:
                logger.exception("Failed to clear state: %s", e)
                await message.answer(SERVICE_ERROR_MESSAGE)
                return
            trip_id = save_trip(
                {
                    "user_id": uid,
                    "origin": slots["origin"],
                    "destination": slots["destination"],
                    "date": slots["date"],
                    "transport": slots["transport"],
                    "status": "pending",
                }
            )
            await notify_manager(trip_id, slots, message.from_user)
            await message.answer(
                REQUEST_SENT_MESSAGE
            )
        else:
            await message.answer(YESNO_PROMPT_USER)
        return

    if state.get("confirm"):
        if "отмен" in message.text.lower():
            try:
                await clear_user_state(uid)
            except StateStorageError as e:
                logger.exception("Failed to clear state: %s", e)
                await message.answer(SERVICE_ERROR_MESSAGE)
                return
            await message.answer(BOOKING_CANCELLED_MESSAGE)
            return

        choice = await parse_yes_no(message.text)
        if choice == "yes":
            missing = get_missing_slots(state)
            if missing:
                question_text = await generate_question(
                    missing[0], DEFAULT_QUESTIONS[missing[0]]
                )
                state["last_question"] = question_text
                state.pop("confirm", None)
                try:
                    await set_user_state(uid, state)
                except StateStorageError as e:
                    logger.exception("Failed to save state: %s", e)
                await message.answer(question_text)
                return
            state.pop("confirm", None)
            state["extra_questions"] = list(EXTRA_QUESTIONS.keys())
            try:
                await set_user_state(uid, state)
            except StateStorageError as e:
                logger.exception("Failed to save state: %s", e)
                await message.answer(SERVICE_ERROR_MESSAGE)
                return
            await message.answer(EXTRA_QUESTIONS[state["extra_questions"][0]])
        else:
            state.pop("confirm", None)
            session_data = {uid: state}
            slots, changed = await update_slots(uid, message.text, session_data)
            state = session_data[uid]
            changed_msg = ""
            if changed:
                parts = [
                    f"{FIELD_NAMES[k]} на {display_transport(v) if k == 'transport' else v}"
                    for k, v in changed.items()
                ]
                changed_msg = "Изменил " + ", ".join(parts) + ".\n"

            missing = get_missing_slots(slots)
            if missing:
                question_text = await generate_question(
                    missing[0], DEFAULT_QUESTIONS[missing[0]]
                )
                state["last_question"] = question_text
                try:
                    await set_user_state(uid, state)
                except StateStorageError as e:
                    logger.exception("Failed to save state: %s", e)
                await message.answer(changed_msg + question_text)
            else:
                summary = await generate_confirmation(
            slots,
            f"Отлично, вот что получилось: {display_transport(slots['transport'])} {slots['origin']} → {slots['destination']} {slots['date']}. Всё верно?",
        )
                await message.answer(changed_msg + summary)
                state["confirm"] = True
                try:
                    await set_user_state(uid, state)
                except StateStorageError as e:
                    logger.exception("Failed to save state: %s", e)
        return

    await handle_slots(message, state)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
