import json
import logging
import re
from datetime import datetime
from typing import Dict, Optional

import aiohttp
import asyncio

from .gpt import (
    API_URL,
    MODEL_URI,
    build_prompt,
    create_session,
    generate_text,
)
from .prompts import (
    SLOTS_PROMPT_TEMPLATE,
    COMPLETE_PROMPT_TEMPLATE,
    QUESTION_PROMPT,
    CONFIRM_PROMPT,
    FALLBACK_PROMPT,
    YESNO_PROMPT,
    HISTORY_PROMPT,
)
from .texts import TRANSPORT_QUESTION_FALLBACK
from .config import YANDEX_IAM_TOKEN

logger = logging.getLogger(__name__)

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
WEEKDAYS_RU = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]
TODAY_WEEKDAY = WEEKDAYS_RU[datetime.now().weekday()]
SLOTS_PROMPT = SLOTS_PROMPT_TEMPLATE.replace("{today_date}", TODAY_DATE).replace(
    "{today_weekday}", TODAY_WEEKDAY
)
COMPLETE_PROMPT = COMPLETE_PROMPT_TEMPLATE.replace("{today_date}", TODAY_DATE).replace(
    "{today_weekday}", TODAY_WEEKDAY
)


async def generate_question(slot: str, fallback: str) -> str:
    """Return friendly question for missing slot via YandexGPT."""
    prompt = build_prompt(QUESTION_PROMPT.format(slot=slot))
    text = await generate_text(prompt)
    return text or fallback


async def generate_confirmation(slots: Dict[str, Optional[str]], fallback: str) -> str:
    """Return booking confirmation message via YandexGPT."""
    prompt = build_prompt(
        CONFIRM_PROMPT.format(
            origin=slots.get("origin", ""),
            destination=slots.get("destination", ""),
            date=slots.get("date", ""),
            transport=slots.get("transport", ""),
        )
    )
    text = await generate_text(prompt)
    return text or fallback


async def generate_fallback(text: str, fallback: str) -> str:
    """Return friendly fallback message via YandexGPT."""
    prompt = build_prompt(FALLBACK_PROMPT.format(text=text))
    result = await generate_text(prompt)
    return result or fallback


def parse_transport(text: str) -> Optional[str]:
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


def _extract_json(text: str) -> str:
    """Return the last valid JSON object from YandexGPT answer.

    Models sometimes return extra data around JSON or even several JSON
    objects one after another. ``json.loads`` fails on such strings with
    ``JSONDecodeError: Extra data``. This helper extracts the last
    decodable JSON object so the caller can safely parse it.
    """
    text = text.strip()
    if text.startswith("```"):
        # Strip code fences like ```json
        text = text.strip("`")
        text = text.lstrip("json").strip()

    # Iterate over potential JSON objects and return the last valid one
    start = None
    depth = 0
    result = None
    for idx, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start : idx + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        if any(k for k in obj.keys()) or result is None:
                            result = candidate
                except json.JSONDecodeError:
                    pass
                start = None
    return result or text


def _safe_int(value, default: int = 0) -> int:
    """Return ``value`` as positive int or ``default`` if not possible."""
    try:
        result = int(value)
        if result > 0:
            return result
    except (TypeError, ValueError):
        pass
    return default


async def parse_slots(
    text: str, question: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """Отправляет текст (и контекст вопроса) в YandexGPT и возвращает словарь слотов."""
    if question:
        text = f"Вопрос: {question}\nОтвет: {text}"
    logger.info("User message: %s", text)
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": 2000,
        },
        "messages": [
            {"role": "system", "text": build_prompt(SLOTS_PROMPT)},
            {"role": "user", "text": text},
        ],
    }
    try:
        async with create_session() as session:
            async with session.post(
                API_URL, headers=headers, json=payload, timeout=30
            ) as response:
                response.raise_for_status()
                data = await response.json()
                answer = (
                    data.get("result", {})
                    .get("alternatives", [{}])[0]
                    .get("message", {})
                    .get("text", "")
                )
                logger.info("Yandex response: %s", answer)
                slots = json.loads(_extract_json(answer))
                return {
                    "origin": slots.get("origin"),
                    "destination": slots.get("destination"),
                    "date": slots.get("date"),
                    "transport": slots.get("transport"),
                }
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception("Failed to parse slots: %s", e)
    except Exception as e:
        logger.exception("Failed to parse slots: %s", e)
    return {"origin": None, "destination": None, "date": None, "transport": None}


async def complete_slots(
    slots: Dict[str, Optional[str]],
    missing: list[str],
) -> tuple[Dict[str, Optional[str]], Optional[str]]:
    """Дополняет или исправляет уже известные слоты через YandexGPT.

    Принимает список незаполненных ``missing`` слотов и запрашивает модель
    только по ним. Если список пуст, запрос к API не выполняется и текущие
    данные возвращаются без изменений.

    Возвращает кортеж ``(slots, question)``, где ``question`` содержит текст
    уточняющего вопроса по транспорту, если он так и не был распознан.
    """
    logger.info("Current slots: %s, missing: %s", slots, missing)

    if not missing:
        logger.info("No missing slots, skipping completion API call")
        return slots, None

    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": 2000,
        },
        "messages": [
            {"role": "system", "text": build_prompt(COMPLETE_PROMPT)},
            {
                "role": "user",
                "text": json.dumps(
                    {k: slots.get(k) for k in missing}, ensure_ascii=False
                ),
            },
        ],
    }
    question: Optional[str] = None
    result = slots
    try:
        async with create_session() as session:
            async with session.post(
                API_URL, headers=headers, json=payload, timeout=30
            ) as response:
                response.raise_for_status()
                data = await response.json()
                answer = (
                    data.get("result", {})
                    .get("alternatives", [{}])[0]
                    .get("message", {})
                    .get("text", "")
                )
                logger.info("Yandex completion: %s", answer)
                updated = json.loads(_extract_json(answer))

                mapping = {
                    "origin": updated.get("origin"),
                    "destination": updated.get("destination"),
                    "date": updated.get("date"),
                    "transport": updated.get("transport"),
                }
                for key in missing:
                    if mapping.get(key):
                        result[key] = mapping[key]
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception("Failed to complete slots: %s", e)
    except Exception as e:
        logger.exception("Failed to complete slots: %s", e)

    if "transport" in missing and not result.get("transport"):
        question = await generate_question("transport", TRANSPORT_QUESTION_FALLBACK)

    return result, question


# --- History requests ------------------------------------------------------


def _heuristic_history(text: str) -> Dict[str, Optional[str]]:
    """Быстрый разбор запроса без GPT для тестов и резервного канала."""
    low = text.lower()
    match = re.search(r"покажи.*?(\d+)", low)
    if "покаж" in low and "поездк" in low:
        limit = int(match.group(1)) if match else 5
        return {"action": "show", "limit": limit, "destination": ""}
    cancel = re.search(r"отмени .*?поездк.*?в\s+([\w\s-]+)", low)
    if cancel:
        return {
            "action": "cancel",
            "destination": cancel.group(1).strip(),
            "limit": 5,
        }
    return {"action": ""}


async def parse_history_request(text: str) -> Dict[str, Optional[str]]:
    """Return structured history command using YandexGPT if available."""
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": 100,
        },
        "messages": [
            {"role": "system", "text": build_prompt(HISTORY_PROMPT)},
            {"role": "user", "text": text},
        ],
    }
    try:
        async with create_session() as session:
            async with session.post(
                API_URL, headers=headers, json=payload, timeout=15
            ) as response:
                response.raise_for_status()
                data = await response.json()
                answer = (
                    data.get("result", {})
                    .get("alternatives", [{}])[0]
                    .get("message", {})
                    .get("text", "")
                )
                logger.info("History request result: %s", answer)
                parsed = json.loads(_extract_json(answer))
                if not isinstance(parsed, dict):
                    parsed = {}
                parsed = {k: v for k, v in parsed.items() if isinstance(k, str) and k}
                action = str(parsed.get("action", "")).strip()
                if action:
                    return {
                        "action": action,
                        "destination": str(parsed.get("destination", "")).strip(),
                        "limit": _safe_int(parsed.get("limit"), default=5),
                    }
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception("Failed to parse history request: %s", e)
    except Exception as e:
        logger.exception("Failed to parse history request: %s", e)
    return _heuristic_history(text)


async def parse_yes_no(text: str) -> str:
    """Return 'yes', 'no' or 'unknown' for arbitrary confirmation text."""
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.1,
            "maxTokens": 20,
        },
        "messages": [
            {"role": "user", "text": build_prompt(YESNO_PROMPT.format(text=text))},
        ],
    }
    try:
        async with create_session() as session:
            async with session.post(
                API_URL, headers=headers, json=payload, timeout=10
            ) as response:
                response.raise_for_status()
                data = await response.json()
                answer = (
                    data.get("result", {})
                    .get("alternatives", [{}])[0]
                    .get("message", {})
                    .get("text", "")
                )
                parsed = json.loads(_extract_json(answer))
                result = parsed.get("result", "").strip().lower()
                if result in {"yes", "no"}:
                    return result
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception("Failed to parse yes/no: %s", e)
    except Exception as e:
        logger.exception("Failed to parse yes/no: %s", e)

    low = text.lower().strip()
    if low in {"да", "ага", "угу", "yes", "yep", "sure", "ок", "окей", "конечно"}:
        return "yes"
    if low in {"нет", "неа", "no", "не", "не надо", "не хочу", "откажусь"}:
        return "no"
    return "unknown"
