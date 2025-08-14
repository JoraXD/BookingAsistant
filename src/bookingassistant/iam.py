import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import jwt  # PyJWT

IAM_ENDPOINT = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
IAM_AUDIENCE = IAM_ENDPOINT
REFRESH_SKEW = 600  # рефреш за 10 минут до истечения

@dataclass
class _TokenState:
    token: Optional[str] = None
    exp_epoch: int = 0         # когда протухнет IAM token
    issued_epoch: int = 0      # когда выпустили (для форс-обновления)

class AsyncIamTokenManager:
    """
    Получает и кэширует IAM-токен по authorized key (sa-key.json) сервисного аккаунта.
    Автоматически обновляет токен, если он скоро истечёт или прошёл форс-интервал.
    """
    def __init__(
        self,
        sa_key_path: str,
        refresh_every_hours: int = 10,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """Initialize manager from service account key or environment token.

        If ``YANDEX_IAM_TOKEN`` is provided in the environment, the service
        account key is not required and the token will be used as-is. This makes
        it possible to run tests or offline scripts without the SA JSON file.
        """

        # Common state initialisation
        self._state = _TokenState()
        self._force_interval = refresh_every_hours * 3600
        self._lock = asyncio.Lock()
        self._session = session  # можно пробросить общий ClientSession

        override = os.getenv("YANDEX_IAM_TOKEN")
        if override:
            # Placeholders so that _build_jwt is never called when override is set
            self._sa_id = ""
            self._key_id = ""
            self._private_key_pem = b""
            return

        try:
            with open(sa_key_path, "r", encoding="utf-8") as f:
                key = json.load(f)
        except FileNotFoundError as e:
            raise RuntimeError(
                "Service account key file not found. Provide YANDEX_SA_KEY_PATH or set YANDEX_IAM_TOKEN."
            ) from e
        except json.JSONDecodeError as e:
            raise RuntimeError("Service account key file is invalid JSON") from e

        self._sa_id: str = key["service_account_id"]
        self._key_id: str = key["id"]
        self._private_key_pem: bytes = key["private_key"].encode("utf-8")

    def _build_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iss": self._sa_id,
            "sub": self._sa_id,
            "aud": IAM_AUDIENCE,
            "iat": now,
            "exp": now + 3600,   # JWT живёт до 1 часа
        }
        headers = {"kid": self._key_id, "alg": "RS256", "typ": "JWT"}
        return jwt.encode(payload, self._private_key_pem, algorithm="RS256", headers=headers)

    def _needs_refresh_unlocked(self) -> bool:
        now = int(time.time())
        if not self._state.token:
            return True
        if now + REFRESH_SKEW >= self._state.exp_epoch:
            return True
        if self._state.issued_epoch and (now - self._state.issued_epoch) >= self._force_interval:
            return True
        return False

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        self._session = aiohttp.ClientSession()
        return self._session

    async def _exchange_jwt_for_iam(self) -> None:
        jwt_token = self._build_jwt()
        session = await self._ensure_session()
        async with session.post(IAM_ENDPOINT, json={"jwt": jwt_token}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()
        iam_token = data["iamToken"]
        # expiresAt: "YYYY-MM-DDTHH:MM:SSZ"
        exp_dt = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
        self._state = _TokenState(
            token=iam_token,
            exp_epoch=int(exp_dt.timestamp()),
            issued_epoch=int(time.time()),
        )

    async def get_token(self) -> str:
        # Позволяем переопределить IAM-токен через переменную окружения,
        # чтобы тесты и офлайн-запуски не обращались к сети.
        override = os.getenv("YANDEX_IAM_TOKEN")
        if override:
            return override

        # Быстрая проверка без блокировки
        if not self._needs_refresh_unlocked():
            return self._state.token  # type: ignore[return-value]

        async with self._lock:
            # Повторная проверка под локом (double-checked locking)
            if not self._needs_refresh_unlocked():
                return self._state.token  # type: ignore[return-value]
            await self._exchange_jwt_for_iam()
            return self._state.token  # type: ignore[return-value]

    async def aclose(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
