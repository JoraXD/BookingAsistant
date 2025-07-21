from datetime import datetime
from typing import Optional

import dateparser


def normalize_date(text: str) -> Optional[str]:
    """Возвращает дату в формате YYYY-MM-DD или None."""
    dt = dateparser.parse(text, languages=['ru'])
    if not dt:
        return None
    dt = dt.replace(tzinfo=None)
    if dt.date() < datetime.now().date():
        return None
    return dt.strftime('%Y-%m-%d')
