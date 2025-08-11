"""Mapping constants used across the project."""

# Correspondence of Russian weekday names to Python's weekday numbers
DAYS_MAP = {
    "понедельник": 0, "пн": 0, "пон": 0,
    "вторник": 1, "вт": 1, "втр": 1,
    "среда": 2, "ср": 2,
    "четверг": 3, "чт": 3, "чет": 3,
    "пятница": 4, "пт": 4, "пятн": 4,
    "суббота": 5, "сб": 5, "суб": 5,
    "воскресенье": 6, "вс": 6, "воскр": 6,
}

# Mapping of internal transport codes to Russian labels
TRANSPORT_RU = {
    'bus': 'автобус',
    'train': 'поезд',
    'plane': 'самолет',
}
