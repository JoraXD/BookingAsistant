"""Загрузка переменных окружения и общие настройки бота."""

import os

from dotenv import load_dotenv

# Подгружаем значения из .env файла
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
YANDEX_SA_KEY_PATH = os.getenv("YANDEX_SA_KEY_PATH", "sa-key.json")
MANAGER_BOT_TOKEN = os.getenv("MANAGER_BOT_TOKEN")
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID")
PAYMENT_DETAILS = os.getenv("PAYMENT_DETAILS", "реквизиты не указаны")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
if not YANDEX_FOLDER_ID:
    raise RuntimeError("YANDEX_FOLDER_ID is not set")
