from datetime import datetime, timedelta
from typing import Optional

import re

import dateparser

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

