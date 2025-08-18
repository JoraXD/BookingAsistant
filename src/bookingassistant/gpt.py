import asyncio
import logging
import ssl
from pathlib import Path
from typing import Any

import aiohttp
import certifi

from .config import (
    YANDEX_FOLDER_ID,
    YANDEX_SA_KEY_PATH,
    YANDEX_API_KEY,
    USE_IAM,
)
from .iam import AsyncIamTokenManager, _TokenState

API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
MODEL_URI = f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite"

# Shared SSL context using certifi certificate bundle
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Singleton IAM manager for the process
IAM = (
    AsyncIamTokenManager(sa_key_path=YANDEX_SA_KEY_PATH, refresh_every_hours=10)
    if USE_IAM
    else None
)


def create_session() -> aiohttp.ClientSession:
    """Return aiohttp session configured with shared SSL context."""
    connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
    return aiohttp.ClientSession(connector=connector)


async def generate_text(
    prompt: str,
    *,
    temperature: float = 0.5,
    top_p: float = 1.0,
    max_tokens: int = 100,
    timeout: int = 15,
) -> str:
    """Call YandexGPT and return the generated text."""
    if USE_IAM:
        headers = {
            "Authorization": f"Bearer {await IAM.get_token()}",
            "Content-Type": "application/json",
        }
    else:
        headers = {
            "Authorization": f"Api-Key {YANDEX_API_KEY}",
            "Content-Type": "application/json",
        }
    payload: dict[str, Any] = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "topP": top_p,
            "maxTokens": max_tokens,
        },
        "messages": [{"role": "user", "text": prompt}],
    }
    try:
        async with create_session() as session:
            async with session.post(
                API_URL, headers=headers, json=payload, timeout=timeout
            ) as response:
                if USE_IAM and response.status == 401:
                    IAM._state = _TokenState()
                    headers["Authorization"] = f"Bearer {await IAM.get_token()}"
                    async with session.post(
                        API_URL, headers=headers, json=payload, timeout=timeout
                    ) as resp2:
                        resp2.raise_for_status()
                        data = await resp2.json()
                        return (
                            data.get("result", {})
                            .get("alternatives", [{}])[0]
                            .get("message", {})
                            .get("text", "")
                            .strip()
                        )
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
        if (
            not USE_IAM
            and isinstance(e, aiohttp.ClientResponseError)
            and e.status in (401, 403)
        ):
            raise
        logging.exception("Failed to generate text: %s", e)
    except Exception as e:  # pragma: no cover - unexpected
        if not USE_IAM:
            raise
        logging.exception("Failed to generate text: %s", e)
    return ""


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    """Return prompt text loaded from prompts directory."""
    with open(PROMPTS_DIR / name, encoding="utf-8") as f:
        return f.read().strip()


NLG_PROMPT = load_prompt("nlg.txt")


def build_prompt(extra: str) -> str:
    """Attach shared header to task-specific part."""
    return f"{NLG_PROMPT} {extra}".strip()
