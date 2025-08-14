"""Booking Assistant package.

This module provides a single entry point that launches both the user
facing bot and the manager bot.  Running ``python -m bookingassistant``
will start them concurrently so there is no need to run two separate
scripts.
"""

from __future__ import annotations

import asyncio

from .main import main as _run_user_bot
from .manager_bot import main as _run_manager_bot


async def run_bots() -> None:
    """Start both bots concurrently."""

    await asyncio.gather(_run_user_bot(), _run_manager_bot())


if __name__ == "__main__":  # pragma: no cover - manual start
    asyncio.run(run_bots())
