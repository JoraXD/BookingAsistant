import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from config import MANAGER_BOT_TOKEN

if not MANAGER_BOT_TOKEN:
    raise RuntimeError("MANAGER_BOT_TOKEN is not set")

bot = Bot(token=MANAGER_BOT_TOKEN)

dp = Dispatcher()

@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer('Здесь будут появляться новые заявки на бронирование.')

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
