import logging
from typing import Dict, Optional

from parser import parse_slots
from utils import normalize_date

logger = logging.getLogger(__name__)


def update_slots(user_id: int, message: str, session_data: Dict[int, Dict[str, Optional[str]]]) -> Dict[str, Optional[str]]:
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
    dict
        Updated slot dictionary for ``user_id``.
    """
    # Current user slots or empty defaults
    slots = session_data.get(user_id, {
        'from': None,
        'to': None,
        'date': None,
        'transport': None,
    })

    logger.info("Editing slots for %s: %s", user_id, message)

    parsed = parse_slots(message)
    user_date = normalize_date(message)
    if user_date:
        parsed['date'] = user_date
    elif parsed.get('date'):
        parsed['date'] = normalize_date(parsed['date']) or parsed['date']

    changed = {}
    for key in ['from', 'to', 'date', 'transport']:
        value = parsed.get(key)
        if value:
            if slots.get(key) != value:
                changed[key] = value
            slots[key] = value

    session_data[user_id] = slots

    if changed:
        logger.info("Updated slots for %s: %s", user_id, changed)
    else:
        logger.info("No slot updates for %s", user_id)

    return slots
