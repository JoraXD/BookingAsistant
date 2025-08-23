import logging
import re
from typing import Dict, Optional, Iterable

from .parser import parse_slots, parse_transport
from .utils import normalize_date
from .maps import DAYS_MAP

logger = logging.getLogger(__name__)


# Common city aliases/abbreviations to recognise in user messages. The values
# are stems or short forms that may appear instead of the full city name.
CITY_ALIASES: dict[str, Iterable[str]] = {
    "москва": ("моск", "мск"),
    "санкт-петербург": ("санкт-петербург", "санкт петербург", "спб", "питер"),
    "екатеринбург": ("екатеринбург", "екб"),
    "казань": ("казан",),
}


def _city_in_message(city: str, message: str) -> bool:
    """Return ``True`` if ``message`` contains ``city`` or its alias."""
    low_city = city.lower()
    aliases = set(CITY_ALIASES.get(low_city, ()))
    aliases.add(low_city[:4])
    return any(alias and alias in message for alias in aliases)


def _detect_city_role(city: str, message: str) -> Optional[str]:
    """Return 'from' or 'to' if preposition before ``city`` indicates direction."""
    low_msg = message.lower()
    aliases = [city.lower(), *CITY_ALIASES.get(city.lower(), ())]
    for alias in aliases:
        if not alias:
            continue
        pattern = rf"\b(из|от|в|во|на)\s+{re.escape(alias)}\w*"
        match = re.search(pattern, low_msg)
        if match:
            prep = match.group(1)
            if prep in {"из", "от"}:
                return "from"
            if prep in {"в", "во", "на"}:
                return "to"
    return None


def _date_in_message(text: str) -> bool:
    """Return True if ``text`` contains explicit date or weekday words."""
    low = text.lower()
    if re.search(r"\b(сегодня|завтра|послезавтра)\b", low):
        return True
    for word in DAYS_MAP:
        if re.search(rf"\b{re.escape(word)}\w*", low):
            return True
    if re.search(r"\d{1,2}[./]\d{1,2}", low) or re.search(r"\b\d{4}-\d{2}-\d{2}\b", low):
        return True
    return False


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
    elif not _date_in_message(message):
        parsed["date"] = None

    user_transport = parse_transport(message)
    if user_transport:
        parsed["transport"] = user_transport
    else:
        parsed["transport"] = None

    # Drop origin/destination values that are not mentioned in the user's
    # message or contradict the detected prepositions to prevent hallucinated
    # cities from overwriting existing slots. If a city clearly has the
    # opposite role (e.g. the model put it in ``from`` but the message says
    # "в Москву"), move it to the proper slot instead of discarding.
    for key in ("from", "to"):
        value = parsed.get(key)
        if not value:
            continue
        role = _detect_city_role(value, low_msg)
        if role and role != key:
            parsed[key] = None
            parsed[role] = value
            continue
        if not role and not _city_in_message(value, low_msg):
            parsed[key] = None

    # If only one city remains, assign it to destination by default unless
    # preposition explicitly marks it as origin.
    unique = {c for c in (parsed.get("from"), parsed.get("to")) if c}
    if len(unique) == 1:
        city = unique.pop()
        role = _detect_city_role(city, low_msg)
        if role == "from":
            parsed["from"] = city
            parsed["to"] = None
        else:
            parsed["from"] = None
            parsed["to"] = city

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
