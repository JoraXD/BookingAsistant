import logging
from typing import Dict, Optional

from .parser import parse_slots
from .models import DEFAULT_CONFIDENCE
from .utils import normalize_date, normalize_transport, validate_city

logger = logging.getLogger(__name__)


async def update_slots(
    user_id: int,
    message: str,
    session_data: Dict[int, Dict[str, Optional[str]]],
    question: Optional[str] = None,
    pre_slots: Optional[Dict[str, Optional[str]]] = None,
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
            "confidence": DEFAULT_CONFIDENCE.copy(),
        },
    )

    logger.info("Editing slots for %s: %s", user_id, message)

    if pre_slots is not None:
        parsed = dict(pre_slots)
    else:
        parsed = await parse_slots(message, question)

    parsed["transport"] = normalize_transport(parsed.get("transport"))
    parsed_conf = parsed.get("confidence", {})

    raw_from = parsed.get("from")
    raw_to = parsed.get("to")
    parsed["from"] = await validate_city(raw_from)
    parsed["to"] = await validate_city(raw_to)
    if parsed["from"] is None and raw_from:
        parsed["from"] = raw_from
        parsed_conf["from"] = 0.0
    if parsed["to"] is None and raw_to:
        parsed["to"] = raw_to
        parsed_conf["to"] = 0.0

    user_date = normalize_date(message)
    if user_date:
        parsed["date"] = user_date
    elif parsed.get("date"):
        parsed["date"] = normalize_date(parsed["date"]) or parsed["date"]

    changed = {}
    conf = slots.get("confidence", DEFAULT_CONFIDENCE.copy())
    for key in ["from", "to", "date", "transport"]:
        value = parsed.get(key)
        if value:
            # If slot already had some value and user provided a new one,
            # consider this an edit and record it. Filling previously empty
            # fields is not treated as a change for notification purposes.
            if slots.get(key) is not None and slots.get(key) != value:
                changed[key] = value
            slots[key] = value
        if key in parsed_conf:
            conf[key] = parsed_conf[key]
    slots["confidence"] = conf

    session_data[user_id] = slots

    if changed:
        logger.info("Updated slots for %s: %s", user_id, changed)
    else:
        logger.info("No slot updates for %s", user_id)

    return slots, changed
