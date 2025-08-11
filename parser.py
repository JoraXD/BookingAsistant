import json
import logging
import re
from datetime import datetime
from typing import Dict, Optional

import aiohttp
import asyncio
import ssl
import certifi

from config import YANDEX_IAM_TOKEN, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)

API_URL = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
MODEL_URI = f'gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite'

# Reuse a single SSL context with certifi's CA bundle to avoid certificate
# verification issues in environments without system certificates
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _session() -> aiohttp.ClientSession:
    """Return ``aiohttp`` session with configured SSL context."""
    return aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT))

TODAY_DATE = datetime.now().strftime('%Y-%m-%d')
WEEKDAYS_RU = [
    'понедельник', 'вторник', 'среда',
    'четверг', 'пятница', 'суббота', 'воскресенье'
]
TODAY_WEEKDAY = WEEKDAYS_RU[datetime.now().weekday()]

BASE_PROMPT = (
    'Ты — дружелюбный помощник по бронированию поездок, представляешь компанию-агрегатор, '
    'к которой обращаются за помощью в поисках билетов. '
    'Общайся как живой человек: используй разные фразы, будь вежлив и сдержан, '
    'помогай догадками, если текст неполный. Не повторяйся.'
)


def build_prompt(extra: str) -> str:
    """Attach shared header to task-specific part."""
    return f"{BASE_PROMPT} {extra}".strip()


SLOTS_PROMPT = (
    'Твоя цель — из любого пользовательского текста извлечь 4 параметра:\n'
    '- origin — город отправления\n'
    '- destination — город назначения\n'
    '- date — дата поездки (формат YYYY-MM-DD)\n'
    '- transport — вид транспорта (bus, train, plane), если не указан — оставь пусто\n'
    '\n‼ ВАЖНЫЕ ПРАВИЛА:\n'
    '1. Понимай и исправляй искаженные слова, сокращения, сленговые названия:\n'
    '   - Город: "питер", "мск", "москоу", "екб", "новосиб", "спб" → нормализуй до официального полного названия ("Санкт-Петербург", "Москва" и т.д.)\n'
    '   - Транспорт: "самолёт", "самолетик", "птичка", "авиабилеты" → plane\n'
    '     "поезд", "электричка", "ржд", "сапсан" → train\n'
    '     "автобус", "маршрутка", "atlas", "шкипер" → bus\n'
    '2. Исправляй опечатки, недостающие буквы, латиницу вместо кириллицы ("Moskva" → "Москва").\n'
    '3. Даты распознавай в любом формате:\n'
    '   - "завтра", "послезавтра", "через неделю", "пятница", "5 авг", "05/08", "2025-08-05"\n'
    '   - Если день/месяц не указан — угадай ближайшую дату.\n'
    '   - Всегда возвращай ISO-формат (YYYY-MM-DD).\n'
    f'   - Если дата указана как день недели (пн, понедельник, в сб, в воскресенье), преобразуй её в ближайшую будущую дату в формате YYYY-MM-DD, считая, что сегодня {TODAY_DATE} {TODAY_WEEKDAY}. Если дата уже прошла на этой неделе, выбери следующую неделю.\n'
    '4. Если есть двусмысленность, выбирай наиболее популярный вариант (например, "Питер" → "Санкт-Петербург").\n'
    '5. Если какой-то параметр отсутствует — оставь пустую строку, но не выдумывай данные.\n'
    '\nВыходной формат строго JSON:\n'
    '{\n'
    '  "origin": "<полное название города или пусто>",\n'
    '  "destination": "<полное название города или пусто>",\n'
    '  "date": "YYYY-MM-DD или пусто",\n'
    '  "transport": "bus/train/plane или пусто"\n'
    '}'
)

COMPLETE_PROMPT = (
    'Ты дополняешь или исправляешь JSON с параметрами поездки. '
    'Если каких-то значений нет, попробуй определить их из текста пользователя. '
    'Требуется вернуть JSON с полями origin, destination, date, transport. '
    'Правила и формат такие же, как и в предыдущей инструкции про извлечение параметров. '
    f'Если дата указана как день недели (пн, понедельник, в сб, в воскресенье), преобразуй её в ближайшую будущую дату в формате YYYY-MM-DD, считая, что сегодня {TODAY_DATE} {TODAY_WEEKDAY}. Если дата уже прошла на этой неделе, выбери следующую неделю.'
)

QUESTION_PROMPT = (
    'Сформулируй короткий вопрос, чтобы узнать "{slot}". Без лишней воды, но красиво и лаконично. '
    'Если это город назначения, уточни куда пользователь хотел бы поехать; если город отправления — откуда отправляется; '
    'если транспорт — спроси, на самолете, автобусе или поезде.'
)

TRANSPORT_QUESTION_FALLBACK = 'Какой транспорт предпочтёте: автобус, поезд или самолёт?'

CONFIRM_PROMPT = (
    'Спроси верно ли бронирование используя данные: '
    'откуда {origin}, куда {destination}, дата {date}, транспорт {transport}. '
    'Скажи коротко и живо, спроси пользователя подтвердить.'
)

FALLBACK_PROMPT = (
    'Пользователь написал: "{text}". Ответь вежливо, что понял не всё, '
    'и попроси уточнить или повторить.'
)

YESNO_PROMPT = (
    'Пользователь сказал: "{text}". Определи, выражает ли он согласие или отказ. '
    'Верни JSON вида {{"result": "yes"}} для согласия, {{"result": "no"}} для отказа '
    'или {{"result": "unknown"}} если однозначно определить нельзя.'
)

HISTORY_PROMPT = (
    'Определи, хочет ли пользователь показать историю поездок или отменить '
    'конкретную поездку. Возвращай JSON:\n'
    '{"action": "show"|"cancel"|"", "destination": "", "limit": <int>}\n'
    'destination указывается только для отмены, limit по умолчанию 5.'
)


async def _generate_text(prompt: str) -> str:
    """Call YandexGPT with a simple text prompt and return the response."""
    headers = {
        'Authorization': f'Bearer {YANDEX_IAM_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'modelUri': MODEL_URI,
        'completionOptions': {
            'stream': False,
            'temperature': 0.5,
            'maxTokens': 100,
        },
        'messages': [{'role': 'user', 'text': prompt}],
    }
    try:
        async with _session() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '').strip()
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception('Failed to generate text: %s', e)
    except Exception as e:
        logger.exception('Failed to generate text: %s', e)
    return ''


async def generate_question(slot: str, fallback: str) -> str:
    """Return friendly question for missing slot via YandexGPT."""
    prompt = build_prompt(QUESTION_PROMPT.format(slot=slot))
    text = await _generate_text(prompt)
    return text or fallback


async def generate_confirmation(slots: Dict[str, Optional[str]], fallback: str) -> str:
    """Return booking confirmation message via YandexGPT."""
    prompt = build_prompt(
        CONFIRM_PROMPT.format(
            origin=slots.get('from', ''),
            destination=slots.get('to', ''),
            date=slots.get('date', ''),
            transport=slots.get('transport', ''),
        )
    )
    text = await _generate_text(prompt)
    return text or fallback


async def generate_fallback(text: str, fallback: str) -> str:
    """Return friendly fallback message via YandexGPT."""
    prompt = build_prompt(FALLBACK_PROMPT.format(text=text))
    result = await _generate_text(prompt)
    return result or fallback


def parse_transport(text: str) -> Optional[str]:
    """Return normalized transport type from free-form text or ``None``."""
    text = text.lower()
    if re.search(r"\b(автобус|маршрутк|atlas|шкипер|bus|бус|бас)\w*", text):
        return "bus"
    if re.search(r"\b(самол[eё]т|самолетик|птичк|авиабилет|plane|полететь|лететь)\w*", text):
        return "plane"
    if re.search(r"\b(поезд|электричк|ржд|сапсан|train|ж.?д)\w*", text):
        return "train"
    return None


def _extract_json(text: str) -> str:
    """Return JSON string from YandexGPT answer."""
    text = text.strip()
    if text.startswith('```'):
        text = text.strip('`')
        text = text.lstrip('json').strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text


async def parse_slots(text: str, question: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Отправляет текст (и контекст вопроса) в YandexGPT и возвращает словарь слотов."""
    if question:
        text = f"Вопрос: {question}\nОтвет: {text}"
    logger.info("User message: %s", text)
    headers = {
        'Authorization': f'Bearer {YANDEX_IAM_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'modelUri': MODEL_URI,
        'completionOptions': {
            'stream': False,
            'temperature': 0.2,
            'maxTokens': 2000,
        },
        'messages': [
            {'role': 'system', 'text': build_prompt(SLOTS_PROMPT)},
            {'role': 'user', 'text': text},
        ],
    }
    try:
        async with _session() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                answer = data.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '')
                logger.info("Yandex response: %s", answer)
                slots = json.loads(_extract_json(answer))
                return {
                    'from': slots.get('origin') or slots.get('from'),
                    'to': slots.get('destination') or slots.get('to'),
                    'date': slots.get('date'),
                    'transport': slots.get('transport'),
                }
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception('Failed to parse slots: %s', e)
    except Exception as e:
        logger.exception('Failed to parse slots: %s', e)
    return {'from': None, 'to': None, 'date': None, 'transport': None}


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
        'Authorization': f'Bearer {YANDEX_IAM_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'modelUri': MODEL_URI,
        'completionOptions': {
            'stream': False,
            'temperature': 0.2,
            'maxTokens': 2000,
        },
        'messages': [
            {'role': 'system', 'text': build_prompt(COMPLETE_PROMPT)},
            {
                'role': 'user',
                'text': json.dumps({k: slots.get(k) for k in missing}, ensure_ascii=False),
            },
        ],
    }
    question: Optional[str] = None
    result = slots
    try:
        async with _session() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                answer = data.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '')
                logger.info("Yandex completion: %s", answer)
                updated = json.loads(_extract_json(answer))

                mapping = {
                    'from': updated.get('origin') or updated.get('from'),
                    'to': updated.get('destination') or updated.get('to'),
                    'date': updated.get('date'),
                    'transport': updated.get('transport'),
                }
                for key in missing:
                    if mapping.get(key):
                        result[key] = mapping[key]
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception('Failed to complete slots: %s', e)
    except Exception as e:
        logger.exception('Failed to complete slots: %s', e)

    if 'transport' in missing and not result.get('transport'):
        question = await generate_question('transport', TRANSPORT_QUESTION_FALLBACK)

    return result, question


# --- History requests ------------------------------------------------------

def _heuristic_history(text: str) -> Dict[str, Optional[str]]:
    """Быстрый разбор запроса без GPT для тестов и резервного канала."""
    low = text.lower()
    match = re.search(r'покажи.*?(\d+)', low)
    if 'покаж' in low and 'поездк' in low:
        limit = int(match.group(1)) if match else 5
        return {'action': 'show', 'limit': limit, 'destination': ''}
    cancel = re.search(r'отмени .*?поездк.*?в\s+([\w\s-]+)', low)
    if cancel:
        return {
            'action': 'cancel',
            'destination': cancel.group(1).strip(),
            'limit': 5,
        }
    return {'action': ''}


async def parse_history_request(text: str) -> Dict[str, Optional[str]]:
    """Return structured history command using YandexGPT if available."""
    headers = {
        'Authorization': f'Bearer {YANDEX_IAM_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'modelUri': MODEL_URI,
        'completionOptions': {
            'stream': False,
            'temperature': 0.2,
            'maxTokens': 100,
        },
        'messages': [
            {'role': 'system', 'text': build_prompt(HISTORY_PROMPT)},
            {'role': 'user', 'text': text},
        ],
    }
    try:
        async with _session() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
                answer = data.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '')
                logger.info('History request result: %s', answer)
                parsed = json.loads(_extract_json(answer))
                action = parsed.get('action', '').strip()
                if action:
                    return {
                        'action': action,
                        'destination': parsed.get('destination', '').strip(),
                        'limit': int(parsed.get('limit', 5) or 5),
                    }
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception('Failed to parse history request: %s', e)
    except Exception as e:
        logger.exception('Failed to parse history request: %s', e)
    return _heuristic_history(text)


async def parse_yes_no(text: str) -> str:
    """Return 'yes', 'no' or 'unknown' for arbitrary confirmation text."""
    headers = {
        'Authorization': f'Bearer {YANDEX_IAM_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'modelUri': MODEL_URI,
        'completionOptions': {
            'stream': False,
            'temperature': 0.1,
            'maxTokens': 20,
        },
        'messages': [
            {'role': 'user', 'text': build_prompt(YESNO_PROMPT.format(text=text))},
        ],
    }
    try:
        async with _session() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                answer = data.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '')
                parsed = json.loads(_extract_json(answer))
                result = parsed.get('result', '').strip().lower()
                if result in {'yes', 'no'}:
                    return result
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logger.exception('Failed to parse yes/no: %s', e)
    except Exception as e:
        logger.exception('Failed to parse yes/no: %s', e)

    low = text.lower().strip()
    if low in {'да', 'ага', 'угу', 'yes', 'yep', 'sure', 'ок', 'окей', 'конечно'}:
        return 'yes'
    if low in {'нет', 'неа', 'no', 'не', 'не надо', 'не хочу', 'откажусь'}:
        return 'no'
    return 'unknown'
