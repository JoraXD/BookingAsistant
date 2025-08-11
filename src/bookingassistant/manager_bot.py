import asyncio
from aiogram import Bot, Dispatcher

"""Бот для менеджера, обрабатывающий заявки от основного сервиса."""

from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from .config import MANAGER_BOT_TOKEN, TELEGRAM_BOT_TOKEN, PAYMENT_DETAILS
from .texts import (
    MANAGER_START_MESSAGE,
    MANAGER_BAD_ID_MESSAGE,
    MANAGER_TRIP_NOT_FOUND_MESSAGE,
    MANAGER_ACCEPTED_TEMPLATE,
    MANAGER_ACCEPTED_USER_TEMPLATE,
    MANAGER_BAD_PARAMS_MESSAGE,
    MANAGER_AWAITING_PAYMENT_TEMPLATE,
    MANAGER_PRICE_USER_TEMPLATE,
    MANAGER_CONFIRMED_TEMPLATE,
    MANAGER_TICKET_CAPTION,
    MANAGER_REJECTED_TEMPLATE,
    MANAGER_REJECTED_USER_TEMPLATE,
    MANAGER_NO_TRIPS_MESSAGE,
    PDF_TICKET_TITLE,
)
from . import storage
from fpdf import FPDF

if not MANAGER_BOT_TOKEN:
    raise RuntimeError("MANAGER_BOT_TOKEN is not set")

bot = Bot(token=MANAGER_BOT_TOKEN)
user_bot = Bot(token=TELEGRAM_BOT_TOKEN)

dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Ответ на команду /start."""
    await message.answer(MANAGER_START_MESSAGE)


def _parse_id(arg: str) -> int | None:
    """Преобразует строковый аргумент в целое id или возвращает ``None``."""
    try:
        return int(arg)
    except (TypeError, ValueError):
        return None


@dp.message(Command("accept"))
async def cmd_accept(message: Message):
    """Пометить заявку как принятую."""
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 1 else None
    if not trip_id:
        await message.answer(MANAGER_BAD_ID_MESSAGE)
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer(MANAGER_TRIP_NOT_FOUND_MESSAGE)
        return
    storage.update_trip_status(trip_id, "accepted")
    await message.answer(MANAGER_ACCEPTED_TEMPLATE.format(trip_id=trip_id))
    await user_bot.send_message(
        trip["user_id"], MANAGER_ACCEPTED_USER_TEMPLATE.format(trip_id=trip_id)
    )


@dp.message(Command("price"))
async def cmd_price(message: Message):
    """Указать цену и запросить оплату у пользователя."""
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 2 else None
    price = parts[2] if len(parts) > 2 else None
    if not trip_id or price is None:
        await message.answer(MANAGER_BAD_PARAMS_MESSAGE)
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer(MANAGER_TRIP_NOT_FOUND_MESSAGE)
        return
    storage.update_trip_status(trip_id, "awaiting_payment")
    await message.answer(MANAGER_AWAITING_PAYMENT_TEMPLATE.format(trip_id=trip_id))
    await user_bot.send_message(
        trip["user_id"],
        MANAGER_PRICE_USER_TEMPLATE.format(
            trip_id=trip_id, price=price, details=PAYMENT_DETAILS
        ),
    )


def _generate_ticket_pdf(trip: dict) -> bytes:
    """Сформировать PDF-билет по данным поездки."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 10, text=PDF_TICKET_TITLE, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        10,
        text=f"Route: {trip['origin']} -> {trip['destination']}\nDate: {trip['date']}\nTransport: {trip['transport']}",
    )
    return bytes(pdf.output(dest="S"))


@dp.message(Command("confirm"))
async def cmd_confirm(message: Message):
    """Подтвердить бронирование и отправить билет пользователю."""
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 1 else None
    if not trip_id:
        await message.answer(MANAGER_BAD_ID_MESSAGE)
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer(MANAGER_TRIP_NOT_FOUND_MESSAGE)
        return
    storage.update_trip_status(trip_id, "confirmed")
    await message.answer(MANAGER_CONFIRMED_TEMPLATE.format(trip_id=trip_id))
    pdf_bytes = _generate_ticket_pdf(trip)
    await user_bot.send_document(
        trip["user_id"],
        BufferedInputFile(pdf_bytes, filename=f"ticket_{trip_id}.pdf"),
        caption=MANAGER_TICKET_CAPTION,
    )


@dp.message(Command("reject"))
async def cmd_reject(message: Message):
    """Отклонить заявку пользователя."""
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 1 else None
    if not trip_id:
        await message.answer(MANAGER_BAD_ID_MESSAGE)
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer(MANAGER_TRIP_NOT_FOUND_MESSAGE)
        return
    storage.update_trip_status(trip_id, "rejected")
    await message.answer(MANAGER_REJECTED_TEMPLATE.format(trip_id=trip_id))
    await user_bot.send_message(
        trip["user_id"], MANAGER_REJECTED_USER_TEMPLATE.format(trip_id=trip_id)
    )


@dp.message(Command("list"))
async def cmd_list(message: Message):
    """Показать список заявок по статусу."""
    parts = message.text.split()
    status = parts[1] if len(parts) > 1 else "pending"
    trips = storage.get_trips_by_status(status)
    if not trips:
        await message.answer(MANAGER_NO_TRIPS_MESSAGE)
        return
    lines = [
        f"<b>{t['id']}</b>: {t['origin']} → {t['destination']} {t['date']} ({t['status']})"
        for t in trips
    ]
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


async def main():
    """Запустить цикл обработки сообщений."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
