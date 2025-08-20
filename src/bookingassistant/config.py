"""Загрузка переменных окружения и общие настройки бота."""

import logging
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

def log_loaded_config() -> None:
    """Вывести все загруженные значения переменных окружения."""
    logger = logging.getLogger(__name__)
    logger.info("TELEGRAM_BOT_TOKEN: %s", TELEGRAM_BOT_TOKEN)
    logger.info("YANDEX_IAM_TOKEN: %s", YANDEX_IAM_TOKEN)
    logger.info("YANDEX_FOLDER_ID: %s", YANDEX_FOLDER_ID)
    logger.info("MANAGER_BOT_TOKEN: %s", MANAGER_BOT_TOKEN)
    logger.info("MANAGER_CHAT_ID: %s", MANAGER_CHAT_ID)
    logger.info("PAYMENT_DETAILS: %s", PAYMENT_DETAILS)
    logger.info("YANDEX_OAUTH_TOKEN: %s", YANDEX_OAUTH_TOKEN)


if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
