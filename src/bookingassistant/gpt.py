import asyncio
import logging
import ssl
from typing import Any
from datetime import datetime, timedelta
import aiohttp
import certifi

from .config import YANDEX_IAM_TOKEN, YANDEX_FOLDER_ID, YANDEX_OAUTH_TOKEN
from .texts import BASE_PROMPT

API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
MODEL_URI = f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite"

# Shared SSL context using certifi certificate bundle
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Глобальные переменные для управления IAM токеном
_iam_token = YANDEX_IAM_TOKEN
_token_expires = None
_token_lock = asyncio.Lock()

def create_session() -> aiohttp.ClientSession:
    """Return aiohttp session configured with shared SSL context."""
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
    return aiohttp.ClientSession(connector=connector)


async def refresh_iam_token() -> str:
    """Refresh IAM token using OAuth token."""
    global _iam_token, _token_expires
    
    headers = {"Content-Type": "application/json"}
    payload = {"yandexPassportOauthToken": YANDEX_OAUTH_TOKEN}
    
    try:
        async with create_session() as session:
            async with session.post(
                "https://iam.api.cloud.yandex.net/iam/v1/tokens",
                headers=headers,
                json=payload,
                timeout=10
            ) as response:
                response.raise_for_status()
                data = await response.json()
                _iam_token = data['iamToken']
                _token_expires = datetime.now() + timedelta(hours=12)
                logging.info("IAM token refreshed successfully")
                return _iam_token
    except Exception as e:
        logging.error("Failed to refresh IAM token: %s", e)
        raise


async def get_valid_iam_token() -> str:
    """Get valid IAM token, refresh if expired."""
    global _iam_token, _token_expires
    
    async with _token_lock:
        # Если токен истек или скоро истечет (менее 5 минут), обновляем
        if (_token_expires is None or 
            datetime.now() > _token_expires - timedelta(minutes=5)):
            return await refresh_iam_token()
        return _iam_token


async def generate_text(
    prompt: str,
    *,
    temperature: float = 0.5,
    max_tokens: int = 100,
    timeout: int = 15,
) -> str:
    """Call YandexGPT and return the generated text."""
    try:
        # Получаем актуальный IAM токен
        iam_token = await get_valid_iam_token()
        
        headers = {
            "Authorization": f"Bearer {iam_token}",
            "Content-Type": "application/json",
        }
        
        payload: dict[str, Any] = {
            "modelUri": MODEL_URI,
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
            "messages": [{"role": "user", "text": prompt}],
        }
        
        async with create_session() as session:
            async with session.post(
                API_URL, headers=headers, json=payload, timeout=timeout
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return (
                    data.get("result", {})
                    .get("alternatives", [{}])[0]
                    .get("message", {})
                    .get("text", "")
                    .strip()
                )
                
    except aiohttp.ClientResponseError as e:
        if e.status == 401:
            logging.warning("Token expired, refreshing...")
            # Пробуем обновить токен и повторить запрос
            iam_token = await refresh_iam_token()
            # Здесь можно добавить ретрай логику
        logging.exception("Failed to generate text: %s", e)
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logging.exception("Failed to generate text: %s", e)
    except Exception as e:
        logging.exception("Unexpected error: %s", e)
    return ""


def build_prompt(extra: str) -> str:
    """Attach shared header to task-specific part."""
    return f"{BASE_PROMPT} {extra}".strip()


# Альтернативный вариант: используйте API Key вместо IAM токена
async def generate_text_with_api_key(
    prompt: str,
    *,
    temperature: float = 0.5,
    max_tokens: int = 100,
    timeout: int = 15,
) -> str:
    """Alternative version using API Key (no expiration)."""
    from .config import YANDEX_API_KEY  # Добавьте это в config.py
    
    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload: dict[str, Any] = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": max_tokens,
        },
        "messages": [{"role": "user", "text": prompt}],
    }
    
    try:
        async with create_session() as session:
            async with session.post(
                API_URL, headers=headers, json=payload, timeout=timeout
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return (
                    data.get("result", {})
                    .get("alternatives", [{}])[0]
                    .get("message", {})
                    .get("text", "")
                    .strip()
                )
    except Exception as e:
        logging.exception("Failed to generate text: %s", e)
        return ""