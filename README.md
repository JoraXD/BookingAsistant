# BookingAssistant

Telegram-бот для интерактивного бронирования поездок. Пользователь вводит произвольный текст, бот извлекает параметры поездки через YandexGPT и уточняет недостающие данные.

## Запуск

1. Создайте файл `.env` со следующими переменными:

```
TELEGRAM_BOT_TOKEN=your_telegram_token
YANDEX_IAM_TOKEN=your_yandex_iam_token
YANDEX_FOLDER_ID=your_folder_id
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Запустите бота:

```bash
python main.py
```

## Команды

- `/start` — начать диалог
- `/cancel` — сбросить текущую сессию
- `/info` или `/help` — инструкция

## Формат результата

После подтверждения бот отправляет JSON с полями `from`, `to`, `date`, `transport`.
