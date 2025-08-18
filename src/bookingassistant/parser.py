import json
import logging
import re
from datetime import datetime
from typing import Dict, Optional

import aiohttp
import asyncio
from pydantic import ValidationError

from .gpt import (
    API_URL,
    MODEL_URI,
    build_prompt,
    create_session,
    generate_text,
    load_prompt,
    IAM,
)
from .iam import _TokenState
from .texts import TRANSPORT_QUESTION_FALLBACK
from .models import SlotsModel, DEFAULT_CONFIDENCE

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

PARSE_SLOTS_PROMPT = load_prompt("parse_slots.txt")
QUESTION_PROMPT = load_prompt("question.txt")
CONFIRM_PROMPT = load_prompt("confirm.txt")
FALLBACK_PROMPT = load_prompt("fallback.txt")
YESNO_PROMPT = load_prompt("yesno.txt")
HISTORY_PROMPT = load_prompt("history.txt")
COMPLETE_PROMPT_TEMPLATE = load_prompt("complete_slots.txt")
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
            origin=slots.get("from", ""),
            destination=slots.get("to", ""),
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
    """Return JSON string from YandexGPT answer."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.lstrip("json").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


async def parse_slots(
    text: str, question: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """Отправляет текст (и контекст вопроса) в YandexGPT и возвращает словарь слотов."""
    if question:
        text = f"Вопрос: {question}\nОтвет: {text}"
    logger.info("User message: %s", text)
    prompt = f"{PARSE_SLOTS_PROMPT}\nТекст: {text}\nJSON:"
    for attempt in range(2):
        try:
            answer = await generate_text(
                prompt,
                temperature=0.1,
                top_p=0.5,
                max_tokens=2000,
                timeout=30,
            )
            logger.info("Yandex response: %s", answer)
            model = SlotsModel.model_validate_json(_extract_json(answer))
            return model.model_dump(by_alias=True)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("Failed to parse slots: %s", e)
            if attempt == 0:
                prompt += (
                    "\nверни строго JSON по схеме {'from': str, 'to': str, 'date': str, "
                    "'transport': 'bus|train|plane', 'confidence': {'from': float, 'to': float, 'date': float, 'transport': float}} без лишнего текста"
                )
                continue
    return SlotsModel().model_dump(by_alias=True)


async def complete_slots(
    payload: Dict[str, Optional[str]],
    missing: list[str],
) -> tuple[Dict[str, Optional[str]], Optional[str]]:
    """Дополняет или исправляет уже известные слоты через YandexGPT.

    ``payload`` должен содержать ключи ``last_question``, ``user_input`` и
    ``known_slots``. В модель отправляются только эти данные без истории
    диалога, что ограничивает размер контекста запроса.

    Возвращает кортеж ``(slots, question)``, где ``question`` содержит текст
    уточняющего вопроса по транспорту, если он так и не был распознан.
    """

    slots = payload.get("known_slots", {})
    logger.info("Current slots: %s, missing: %s", slots, missing)

    if not missing:
        logger.info("No missing slots, skipping completion API call")
        return slots, None

    data = {
        "last_question": payload.get("last_question"),
        "user_input": payload.get("user_input"),
        "known_slots": slots,
    }
    prompt = build_prompt(
        f"{COMPLETE_PROMPT}\n{json.dumps(data, ensure_ascii=False)}\nJSON:"
    )

    question: Optional[str] = None
    result = dict(slots)
    confidence = result.get("confidence", DEFAULT_CONFIDENCE.copy())

    try:
        answer = await generate_text(
            prompt,
            temperature=0.2,
            top_p=0.5,
            max_tokens=2000,
            timeout=30,
        )
        logger.info("Yandex completion: %s", answer)
        try:
            updated = SlotsModel.model_validate_json(
                _extract_json(answer)
            ).model_dump(by_alias=True)
            for key in missing:
                if updated.get(key):
                    result[key] = updated[key]
                if updated.get("confidence") and key in updated["confidence"]:
                    confidence[key] = updated["confidence"][key]
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("Failed to parse completion: %s", e)
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception("Failed to complete slots: %s", e)
    except Exception as e:  # pragma: no cover - unexpected
        logger.exception("Failed to complete slots: %s", e)

    if "transport" in missing and not result.get("transport"):
        question = await generate_question("transport", TRANSPORT_QUESTION_FALLBACK)

    result["confidence"] = confidence

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
        "Authorization": f"Bearer {await IAM.get_token()}",
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
                if response.status == 401:
                    IAM._state = _TokenState()
                    headers["Authorization"] = f"Bearer {await IAM.get_token()}"
                    async with session.post(
                        API_URL, headers=headers, json=payload, timeout=15
                    ) as resp2:
                        resp2.raise_for_status()
                        data = await resp2.json()
                        answer = (
                            data.get("result", {})
                            .get("alternatives", [{}])[0]
                            .get("message", {})
                            .get("text", "")
                        )
                        logger.info("History request result: %s", answer)
                        parsed = json.loads(_extract_json(answer))
                        action = parsed.get("action", "").strip()
                        if action:
                            return {
                                "action": action,
                                "destination": parsed.get("destination", "").strip(),
                                "limit": int(parsed.get("limit", 5) or 5),
                            }
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
                action = parsed.get("action", "").strip()
                if action:
                    return {
                        "action": action,
                        "destination": parsed.get("destination", "").strip(),
                        "limit": int(parsed.get("limit", 5) or 5),
                    }
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception("Failed to parse history request: %s", e)
    except Exception as e:
        logger.exception("Failed to parse history request: %s", e)
    return _heuristic_history(text)


async def parse_yes_no(text: str) -> str:
    """Return 'yes', 'no' or 'unknown' for arbitrary confirmation text."""
    headers = {
        "Authorization": f"Bearer {await IAM.get_token()}",
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
                if response.status == 401:
                    IAM._state = _TokenState()
                    headers["Authorization"] = f"Bearer {await IAM.get_token()}"
                    async with session.post(
                        API_URL, headers=headers, json=payload, timeout=10
                    ) as resp2:
                        resp2.raise_for_status()
                        data = await resp2.json()
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
