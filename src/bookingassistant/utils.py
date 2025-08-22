import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict

import dateparser

from .gpt import build_prompt, generate_text
from .maps import DAYS_MAP, TRANSPORT_RU
from .prompts import TIME_PROMPT


def detect_transport(text: str) -> Optional[str]:
    """Return normalized transport type from free-form text or ``None``."""
    text = text.lower()
    if re.search(r"\b(автобус|маршрутк|atlas|шкипер|bus|бус|бас)\w*", text):
        return "bus"
    if re.search(
        r"\b(самол[eё]т|самолетик|птичк|авиабилет|plane|полететь|лететь)\w*", text
    ):
        return "plane"
    if re.search(r"\b(поезд|электричк|ржд|сапсан|train|ж.?д)\w*", text):
        return "train"
    return None


def pre_extract_slots(text: str) -> Dict[str, Optional[str]]:
    """Быстрая эвристическая попытка извлечь основные слоты из текста."""
    transport = detect_transport(text)
    date = normalize_date(text)
    if not date:
        try:
            from dateparser.search import search_dates

            found = search_dates(text, languages=["ru"])
            if found:
                date = normalize_date(found[0][0])
        except Exception:
            pass

    origin = destination = None

    # Patterns: "из X в Y" or "в Y из X"
    match = re.search(
        r"из\s+([A-Za-zА-Яа-яЁё\s-]+)\s+в\s+([A-Za-zА-Яа-яЁё\s-]+)",
        text,
        flags=re.IGNORECASE,
    )
    def _clean(name: str) -> str:
        return re.split(r"\s+на\s+", name, 1)[0].strip().title()

    if match:
        origin = _clean(match.group(1))
        destination = _clean(match.group(2))
    else:
        match = re.search(
            r"в\s+([A-Za-zА-Яа-яЁё\s-]+)\s+из\s+([A-Za-zА-Яа-яЁё\s-]+)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            destination = _clean(match.group(1))
            origin = _clean(match.group(2))

    return {"from": origin, "to": destination, "date": date, "transport": transport}


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

    dt = dateparser.parse(text, languages=["ru"])
    if not dt:
        return None
    dt = dt.replace(tzinfo=None)
    if dt.date() < datetime.now().date():
        return None
    return dt.strftime("%Y-%m-%d")


async def normalize_time(text: str) -> Optional[str]:
    """Получает время через YandexGPT и возвращает HH:MM или None."""
    prompt = build_prompt(TIME_PROMPT.format(text=text))
    try:
        result = await generate_text(prompt)
    except Exception as e:
        logging.exception("Failed to parse time via GPT: %s", e)
        result = ""

    # Попытка извлечь время из ответа модели
    match = re.search(r"(\d{1,2})(?:[:.](\d{1,2}))?", result)
    if not match:
        # в крайнем случае попробуем извлечь из исходного текста
        match = re.search(r"(\d{1,2})(?:[:.](\d{1,2}))?", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    return f"{hour:02d}:{minute:02d}"


def display_transport(value: Optional[str]) -> str:
    """Return Russian name for a transport code."""
    if not value:
        return "не указан"
    return TRANSPORT_RU.get(value.lower(), value)
