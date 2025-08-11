from datetime import datetime, timedelta
from typing import Optional

import re
import logging

import dateparser
from parser import build_prompt, _generate_text

# Словарь соответствий дней недели
DAYS_MAP = {
    "понедельник": 0, "пн": 0, "пон": 0,
    "вторник": 1, "вт": 1, "втр": 1,
    "среда": 2, "ср": 2,
    "четверг": 3, "чт": 3, "чет": 3,
    "пятница": 4, "пт": 4, "пятн": 4,
    "суббота": 5, "сб": 5, "суб": 5,
    "воскресенье": 6, "вс": 6, "воскр": 6,
}


def next_weekday(target_word: str) -> str:
    """Return next date for given weekday word in YYYY-MM-DD."""
    today = datetime.now()
    weekday_today = today.weekday()  # 0 = понедельник
    target = DAYS_MAP.get(target_word.lower())
    if target is None:
        return ""
    days_ahead = (target - weekday_today) % 7
    if days_ahead == 0:
        days_ahead = 7
    date_result = today + timedelta(days=days_ahead)
    return date_result.strftime("%Y-%m-%d")


def normalize_date(text: str) -> Optional[str]:
    """Возвращает дату в формате YYYY-MM-DD или None."""
    text_lower = text.lower()
    for word in DAYS_MAP:
        if re.search(rf"\b{re.escape(word)}\w*", text_lower):
            date_str = next_weekday(word)
            if date_str:
                return date_str

    dt = dateparser.parse(text, languages=['ru'])
    if not dt:
        return None
    dt = dt.replace(tzinfo=None)
    if dt.date() < datetime.now().date():
        return None
    return dt.strftime('%Y-%m-%d')


# Промпт для получения времени через YandexGPT
TIME_PROMPT = (
    'Определи время из текста: "{text}". '
    'Верни только время в формате HH:MM (24-часовой). '
    'Если распознать не удаётся, верни пустую строку.'
)


async def normalize_time(text: str) -> Optional[str]:
    """Получает время через YandexGPT и возвращает HH:MM или None."""
    prompt = build_prompt(TIME_PROMPT.format(text=text))
    try:
        result = await _generate_text(prompt)
    except Exception as e:
        logging.exception("Failed to parse time via GPT: %s", e)
        result = ''

    # Попытка извлечь время из ответа модели
    match = re.search(r'(\d{1,2})(?:[:.](\d{1,2}))?', result)
    if not match:
        # в крайнем случае попробуем извлечь из исходного текста
        match = re.search(r'(\d{1,2})(?:[:.](\d{1,2}))?', text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    return f"{hour:02d}:{minute:02d}"


# Mapping of internal transport codes to Russian labels
TRANSPORT_RU = {
    'bus': 'автобус',
    'train': 'поезд',
    'plane': 'самолет',
}


def display_transport(value: Optional[str]) -> str:
    """Return Russian name for a transport code."""
    if not value:
        return 'не указан'
    return TRANSPORT_RU.get(value.lower(), value)

