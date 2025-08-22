import logging
from typing import Dict, Optional

from .parser import parse_slots
from .utils import normalize_date, pre_extract_slots

logger = logging.getLogger(__name__)


async def update_slots(
    user_id: int,
    message: str,
    session_data: Dict[int, Dict[str, Optional[str]]],
    question: Optional[str] = None,
) -> tuple[Dict[str, Optional[str]], Dict[str, str], bool, set[str]]:
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
        ``(slots, changed, used_llm, touched)`` where ``slots`` is the updated
        slot dictionary, ``changed`` contains only the fields that were
        modified, ``used_llm`` indicates whether a call to YandexGPT was
        performed, and ``touched`` lists the slots mentioned in the message.
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

    pre = pre_extract_slots(message)
    touched = {k for k, v in pre.items() if v}
    conflict = any(
        slots.get(k) and pre.get(k) and slots.get(k) != pre.get(k)
        for k in ["from", "to", "date", "transport"]
    )
    filled = sum(1 for v in pre.values() if v)
    used_llm = False
    parsed = pre

    if filled < 3 or conflict:
        parsed = await parse_slots(message, question)
        touched = {k for k, v in parsed.items() if v}
        used_llm = True
        user_date = normalize_date(message)
        if user_date:
            parsed["date"] = user_date
        elif parsed.get("date"):
            parsed["date"] = normalize_date(parsed["date"]) or parsed["date"]
        # fallback to heuristic values for missing fields
        for k, v in pre.items():
            if v and not parsed.get(k):
                parsed[k] = v
                touched.add(k)

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

    return slots, changed, used_llm, touched
