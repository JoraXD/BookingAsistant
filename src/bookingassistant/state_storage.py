import json
import os
from typing import Any, Optional

import asyncpg


class StateStorageError(Exception):
    """Raised when state storage operation fails."""

    pass


DATABASE_URL = os.getenv(
    "STATE_DB_URL", "postgresql://postgres:postgres@localhost:5543/template1"
)
_pool: Optional[asyncpg.Pool] = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_state (
                    user_id BIGINT PRIMARY KEY,
                    state JSONB
                )
                """
            )
    return _pool


async def get_user_state(user_id: int) -> Optional[dict[str, Any]]:
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state FROM user_state WHERE user_id=$1", user_id
            )
            return (
                json.loads(row["state"]) if row and row["state"] is not None else None
            )
    except Exception as e:
        raise StateStorageError(str(e)) from e


async def set_user_state(user_id: int, state: dict[str, Any]) -> None:
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_state(user_id, state)
                VALUES($1, $2)
                ON CONFLICT (user_id)
                DO UPDATE SET state=EXCLUDED.state
                """,
                user_id,
                json.dumps(state),
            )
    except Exception as e:
        raise StateStorageError(str(e)) from e


async def clear_user_state(user_id: int) -> None:
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM user_state WHERE user_id=$1", user_id)
    except Exception as e:
        raise StateStorageError(str(e)) from e
