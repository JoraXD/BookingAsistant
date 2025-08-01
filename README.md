# BookingAssistant

Telegram-бот для интерактивного бронирования поездок. Пользователь вводит произвольный текст, бот извлекает параметры поездки через YandexGPT и уточняет недостающие данные. Все уточняющие вопросы и финальное подтверждение формируются моделью, поэтому ответы звучат каждый раз по-разному.

Бот сам распознаёт даты в сообщении пользователя (например, «завтра» или «в субботу»), используя `dateparser`, и переводит их в формат `YYYY-MM-DD`. Если дата в тексте не найдена, используется значение из ответа YandexGPT.

Если выбран транспорт «автобус», после подтверждения бот формирует ссылку вида `https://atlasbus.ru/Маршруты/ГородA/ГородB?date=YYYY-MM-DD` и проверяет, что страница доступна. Если она не выдаёт ошибку 404, бот отправляет ссылку пользователю, иначе пишет, что рейсы не найдены.

## Запуск

1. Создайте файл `.env` со следующими переменными:

```
TELEGRAM_BOT_TOKEN=your_telegram_token
YANDEX_IAM_TOKEN=your_yandex_iam_token
YANDEX_FOLDER_ID=your_folder_id
MANAGER_BOT_TOKEN=manager_bot_token
MANAGER_CHAT_ID=manager_chat_id
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Запустите пользовательского бота:

```bash
python main.py
```

4. Запустите бота менеджера (при необходимости):
```bash
python manager_bot.py
```

## Команды

- `/start` — начать диалог
- `/cancel` — сбросить текущую сессию
- `/info` или `/help` — инструкция
- Можно попросить в свободной форме: "покажи последние поездки" или
  "отмени поездку в <город>"

## История поездок

Подтверждённые бронирования сохраняются в базу SQLite `trips.db`. Команда
Запросы на просмотр истории и отмену тоже обрабатываются через YandexGPT.
Например, "покажи мои поездки за последний месяц" вернёт последние записи,
а "отмени поездку в Москву" найдёт подходящую активную запись и пометит её
отменённой.

## Формат результата

После подтверждения бот отправляет пользователю сообщение в формате JSON:
```json
{
  "message": "Отправили заявку менеджеру, скоро с вами свяжутся!"
}
```
Данные заявки при этом пересылаются в чат `MANAGER_CHAT_ID` через бота с токеном `MANAGER_BOT_TOKEN`.
