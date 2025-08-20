"""Загрузка переменных окружения и общие настройки бота."""

import os

from dotenv import load_dotenv

# Подгружаем значения из .env файла
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YANDEX_IAM_TOKEN = os.getenv("YANDEX_IAM_TOKEN")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
MANAGER_BOT_TOKEN = os.getenv("MANAGER_BOT_TOKEN")
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID")
PAYMENT_DETAILS = os.getenv("PAYMENT_DETAILS", "реквизиты не указаны")
YANDEX_OAUTH_TOKEN = os.getenv("YANDEX_OAUTH_TOKEN")

print("TELEGRAM_BOT_TOKEN:", TELEGRAM_BOT_TOKEN)
print("YANDEX_IAM_TOKEN:", YANDEX_IAM_TOKEN)
print("YANDEX_FOLDER_ID:", YANDEX_FOLDER_ID)
print("MANAGER_BOT_TOKEN:", MANAGER_BOT_TOKEN)
print("MANAGER_CHAT_ID:", MANAGER_CHAT_ID)
print("PAYMENT_DETAILS:", PAYMENT_DETAILS)
print("YANDEX_OAUTH_TOKEN:", YANDEX_OAUTH_TOKEN)

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
