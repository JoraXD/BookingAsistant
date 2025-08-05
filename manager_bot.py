import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from config import MANAGER_BOT_TOKEN, TELEGRAM_BOT_TOKEN
import storage

if not MANAGER_BOT_TOKEN:
    raise RuntimeError("MANAGER_BOT_TOKEN is not set")

bot = Bot(token=MANAGER_BOT_TOKEN)
user_bot = Bot(token=TELEGRAM_BOT_TOKEN)

dp = Dispatcher()


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer('Здесь будут появляться новые заявки на бронирование.')


def _parse_id(arg: str) -> int | None:
    try:
        return int(arg)
    except (TypeError, ValueError):
        return None


@dp.message(Command('approve'))
async def cmd_approve(message: Message):
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 1 else None
    if not trip_id:
        await message.answer('Некорректный ID заявки')
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer('Заявка не найдена')
        return
    storage.update_trip_status(trip_id, 'approved')
    await message.answer(f"Заявка {trip_id} одобрена")
    await user_bot.send_message(trip['user_id'], f"Вашу заявку №{trip_id} одобрили")


@dp.message(Command('reject'))
async def cmd_reject(message: Message):
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 1 else None
    if not trip_id:
        await message.answer('Некорректный ID заявки')
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer('Заявка не найдена')
        return
    storage.update_trip_status(trip_id, 'rejected')
    await message.answer(f"Заявка {trip_id} отклонена")
    await user_bot.send_message(trip['user_id'], f"Вашу заявку №{trip_id} отклонили")


@dp.message(Command('list'))
async def cmd_list(message: Message):
    parts = message.text.split()
    status = parts[1] if len(parts) > 1 else 'pending'
    trips = storage.get_trips_by_status(status)
    if not trips:
        await message.answer('Заявки не найдены')
        return
    lines = [
        f"<b>{t['id']}</b>: {t['origin']} → {t['destination']} {t['date']} ({t['status']})" for t in trips
    ]
    await message.answer('\n'.join(lines), parse_mode=ParseMode.HTML)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
