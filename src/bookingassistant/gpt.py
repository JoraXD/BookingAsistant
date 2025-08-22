import asyncio
import logging
import ssl
from typing import Any

import aiohttp
import certifi

from .config import YANDEX_IAM_TOKEN, YANDEX_FOLDER_ID
from .prompts import BASE_PROMPT

API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
MODEL_URI = f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite"

# Shared SSL context using certifi certificate bundle
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def create_session() -> aiohttp.ClientSession:
    """Return aiohttp session configured with shared SSL context."""
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
    return aiohttp.ClientSession(connector=connector)


async def generate_text(
    prompt: str,
    *,
    temperature: float = 0.5,
    max_tokens: int = 100,
    timeout: int = 15,
) -> str:
    """Call YandexGPT and return the generated text."""
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
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
    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        logging.exception("Failed to generate text: %s", e)
    except Exception as e:  # pragma: no cover - unexpected
        logging.exception("Failed to generate text: %s", e)
    return ""


def build_prompt(extra: str) -> str:
    """Attach shared header to task-specific part."""
    return f"{BASE_PROMPT} {extra}".strip()
