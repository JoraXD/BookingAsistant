import os

# Provide default environment variables required by bookingassistant.config
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:" + "A" * 35)
os.environ.setdefault("YANDEX_IAM_TOKEN", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")
