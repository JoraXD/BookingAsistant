import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import dateparser

from .gpt import build_prompt, generate_text, load_prompt
from .maps import DAYS_MAP, TRANSPORT_RU

TIME_PROMPT = load_prompt("time.txt")


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


def pre_extract_slots(text: str) -> dict:
    """Extract basic slots from text using simple heuristics.

    Attempts to determine transport type, origin, destination and date without
    invoking the LLM. Only very naive patterns are used; if something cannot be
    extracted it is returned as ``None``.
    """

    slots = {"from": None, "to": None, "date": None, "transport": None}

    try:
        from .parser import parse_transport
    except Exception:  # pragma: no cover - import guard
        parse_transport = None

    if parse_transport:
        slots["transport"] = parse_transport(text)

    slots["date"] = normalize_date(text)
    if not slots["date"]:
        try:
            from dateparser.search import search_dates

            found = search_dates(text, languages=["ru"])
            if found:
                dt = found[0][1]
                if dt.date() >= datetime.now().date():
                    slots["date"] = dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    pattern = re.search(
        r"\bиз\s+([A-ZА-ЯЁ][\w-]+)\b.*?\bв\s+([A-ZА-ЯЁ][\w-]+)\b",
        text,
        re.IGNORECASE,
    )
    if pattern:
        slots["from"] = pattern.group(1)
        slots["to"] = pattern.group(2)
    else:
        pattern = re.search(
            r"\bв\s+([A-ZА-ЯЁ][\w-]+)\b.*?\bиз\s+([A-ZА-ЯЁ][\w-]+)\b",
            text,
            re.IGNORECASE,
        )
        if pattern:
            slots["to"] = pattern.group(1)
            slots["from"] = pattern.group(2)

    return slots
