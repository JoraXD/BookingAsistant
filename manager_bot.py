import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from config import MANAGER_BOT_TOKEN, TELEGRAM_BOT_TOKEN, PAYMENT_DETAILS
import storage
from fpdf import FPDF
import json

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


@dp.message(Command('accept'))
async def cmd_accept(message: Message):
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 1 else None
    if not trip_id:
        await message.answer('Некорректный ID заявки')
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer('Заявка не найдена')
        return
    storage.update_trip_status(trip_id, 'accepted')
    await message.answer(f"Заявка {trip_id} принята")
    await user_bot.send_message(trip['user_id'], f"Вашу заявку №{trip_id} приняли в работу")


@dp.message(Command('price'))
async def cmd_price(message: Message):
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 2 else None
    price = parts[2] if len(parts) > 2 else None
    if not trip_id or price is None:
        await message.answer('Некорректные параметры команды')
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer('Заявка не найдена')
        return
    storage.update_trip_status(trip_id, 'awaiting_payment')
    await message.answer(f"Заявка {trip_id} ожидает оплаты")
    await user_bot.send_message(
        trip['user_id'],
        f"Стоимость вашей заявки №{trip_id}: {price}. Оплатите по реквизитам: {PAYMENT_DETAILS}"
    )


def _generate_ticket_pdf(trip: dict) -> bytes:
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()
    pdf.set_font('Helvetica', size=14)
    pdf.cell(0, 10, 'Ticket', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(10)
    pdf.set_font('Helvetica', size=12)
    info = (
        f"Route: {trip['origin']} -> {trip['destination']}\n"
        f"Date: {trip['date']}\n"
        f"Transport: {trip['transport']}"
    )
    contact = trip.get('contact')
    if contact:
        try:
            passengers = json.loads(contact)
        except Exception:
            passengers = None
        if isinstance(passengers, list):
            info += "\nPassengers:"
            for p in passengers:
                name = p.get('fio') or p.get('name', '')
                phone = p.get('phone', '')
                info += f"\n- {name}: {phone}"
        else:
            info += f"\nContact: {contact}"
    pdf.multi_cell(0, 10, info)
    return bytes(pdf.output(dest='S'))


@dp.message(Command('confirm'))
async def cmd_confirm(message: Message):
    parts = message.text.split()
    trip_id = _parse_id(parts[1]) if len(parts) > 1 else None
    if not trip_id:
        await message.answer('Некорректный ID заявки')
        return
    trip = storage.get_trip(trip_id)
    if not trip:
        await message.answer('Заявка не найдена')
        return
    storage.update_trip_status(trip_id, 'confirmed')
    await message.answer(f"Заявка {trip_id} подтверждена")
    pdf_bytes = _generate_ticket_pdf(trip)
    await user_bot.send_document(
        trip['user_id'],
        BufferedInputFile(pdf_bytes, filename=f'ticket_{trip_id}.pdf'),
        caption='Оплата получена, ваш билет готов'
    )


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
