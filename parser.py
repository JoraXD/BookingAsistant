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
    'Ты извлекаешь параметры поездки пользователя. '
    'Нужно вернуть JSON с полями from, to, date, transport. '
    'Если поле не указано, значение null. '
    'Формат даты YYYY-MM-DD.'
)

# Используется при дополнении уже известных слотов
COMPLETE_PROMPT = (
    'Ты дополняешь или исправляешь JSON с параметрами поездки. '
    'Нужно вернуть JSON с полями from, to, date, transport. '
    'Если поле не указано, значение null. '
    'Формат даты YYYY-MM-DD.'
)


def _extract_json(text: str) -> str:
    """Return JSON string from YandexGPT answer."""
    # remove code fences like ```json ... ```
    text = text.strip()
    if text.startswith('```'):
        # strip the opening and closing fences
        text = text.strip('`')
        text = text.lstrip('json').strip()
    # find first JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def _extract_json(text: str) -> str:
    """Return JSON string from YandexGPT answer."""
    # remove code fences like ```json ... ```
    text = text.strip()
    if text.startswith('```'):
        # strip the opening and closing fences
        text = text.strip('`')
        text = text.lstrip('json').strip()
    # find first JSON object
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
            'from': slots.get('from'),
            'to': slots.get('to'),
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
            'from': updated.get('from'),
            'to': updated.get('to'),
            'date': updated.get('date'),
            'transport': updated.get('transport'),
        }
    except Exception as e:
        logger.exception('Failed to complete slots: %s', e)
        return slots
