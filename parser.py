import json
import logging
import re
from typing import Dict, Optional

import requests

from config import YANDEX_IAM_TOKEN, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)

API_URL = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
MODEL_URI = f'gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite'

SYSTEM_PROMPT = (
    'Ты — умный ассистент по бронированию поездок. '
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

# Используется при дополнении уже известных слотов
COMPLETE_PROMPT = (
    'Ты дополняешь или исправляешь JSON с параметрами поездки. '
    'Если каких-то значений нет, попробуй определить их из текста пользователя. '
    'Требуется вернуть JSON с полями origin, destination, date, transport. '
    'Правила и формат такие же, как и в предыдущей инструкции про извлечение параметров.'
)


def parse_transport(text: str) -> str:
    """Return normalized transport type from free-form text."""
    text = text.lower()
    if re.search(r"\b(автобус|маршрутк|atlas|шкипер|bus|бус|бас)\w*", text):
        return "bus"
    if re.search(r"\b(самол[eё]т|самолетик|птичк|авиабилет|plane|полететь|лететь)\w*", text):
        return "plane"
    if re.search(r"\b(поезд|электричк|ржд|сапсан|train|ж.?д)\w*", text):
        return "train"
    return "train"


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


def parse_slots(text: str, question: Optional[str] = None) -> Dict[str, Optional[str]]:
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
            {'role': 'system', 'text': SYSTEM_PROMPT},
            {'role': 'user', 'text': text},
        ],
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        answer = data.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '')
        logger.info("Yandex response: %s", answer)
        slots = json.loads(_extract_json(answer))
        return {
            'from': slots.get('origin') or slots.get('from'),
            'to': slots.get('destination') or slots.get('to'),
            'date': slots.get('date'),
            'transport': slots.get('transport'),
        }
    except Exception as e:
        logger.exception('Failed to parse slots: %s', e)
        return {'from': None, 'to': None, 'date': None, 'transport': None}


def complete_slots(slots: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    """Дополняет или исправляет уже известные слоты через YandexGPT."""
    logger.info("Current slots: %s", slots)
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
            {'role': 'system', 'text': COMPLETE_PROMPT},
            {'role': 'user', 'text': json.dumps(slots, ensure_ascii=False)},
        ],
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        answer = data.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '')
        logger.info("Yandex completion: %s", answer)
        updated = json.loads(_extract_json(answer))

        return {
            'from': updated.get('origin') or updated.get('from'),
            'to': updated.get('destination') or updated.get('to'),
            'date': updated.get('date'),
            'transport': updated.get('transport'),
        }
    except Exception as e:
        logger.exception('Failed to complete slots: %s', e)
        return slots
