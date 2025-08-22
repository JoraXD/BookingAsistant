import logging
from typing import Dict, Optional

from .parser import parse_slots, parse_transport
from .utils import normalize_date

logger = logging.getLogger(__name__)


async def update_slots(
    user_id: int,
    message: str,
    session_data: Dict[int, Dict[str, Optional[str]]],
    question: Optional[str] = None,
) -> tuple[Dict[str, Optional[str]], Dict[str, str]]:
    """Update saved slots for a user based on correction message.

    The function re-parses the incoming ``message`` to detect which booking
    parameters were changed and updates ``session_data`` in place. Only slots
    explicitly mentioned in ``message`` are overwritten. Missing values are
    preserved.

    Parameters
    ----------
    user_id: int
        Telegram user identifier.
    message: str
        New user message containing corrections.
    session_data: dict
        Mapping ``user_id -> slots`` with previously gathered data.

    Returns
    -------
    tuple
        ``(slots, changed)`` where ``slots`` is the updated slot dictionary and
        ``changed`` contains only the fields that were modified. Filling
        previously empty slots is not considered a modification.
    """
    # Current user slots or empty defaults
    slots = session_data.get(
        user_id,
        {
            "from": None,
            "to": None,
            "date": None,
            "transport": None,
        },
    )

    logger.info("Editing slots for %s: %s", user_id, message)

    parsed = await parse_slots(message, question)
    low_msg = message.lower()

    # Validate and override date/transport with local heuristics based on
    # the actual user message so that the bot does not invent unseen data.
    user_date = normalize_date(message)
    if user_date:
        parsed["date"] = user_date
    else:
        parsed["date"] = None

    user_transport = parse_transport(message)
    if user_transport:
        parsed["transport"] = user_transport
    else:
        parsed["transport"] = None

    # Drop origin/destination values that are not literally mentioned in
    # the user's message to prevent hallucinated cities from overwriting
    # existing slots.
    for key in ("from", "to"):
        value = parsed.get(key)
        if value:
            prefix = value.lower()[:4]
            if prefix and prefix not in low_msg:
                parsed[key] = None

    changed = {}
    for key in ["from", "to", "date", "transport"]:
        value = parsed.get(key)
        if value:
            # If slot already had some value and user provided a new one,
            # consider this an edit and record it. Filling previously empty
            # fields is not treated as a change for notification purposes.
            if slots.get(key) is not None and slots.get(key) != value:
                changed[key] = value
            slots[key] = value

    session_data[user_id] = slots

    if changed:
        logger.info("Updated slots for %s: %s", user_id, changed)
    else:
        logger.info("No slot updates for %s", user_id)

    return slots, changed
