import os
import datetime

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'x')
os.environ.setdefault('YANDEX_IAM_TOKEN', 'x')
os.environ.setdefault('YANDEX_FOLDER_ID', 'x')

from bookingassistant.utils import next_weekday, normalize_date

class FixedDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2025, 7, 28)

def test_next_weekday(monkeypatch):
    monkeypatch.setattr('bookingassistant.utils.datetime', FixedDatetime)
    assert next_weekday('пт') == '2025-08-01'
    assert next_weekday('вс') == '2025-08-03'

def test_normalize_date_weekday(monkeypatch):
    monkeypatch.setattr('bookingassistant.utils.datetime', FixedDatetime)
    assert normalize_date('в пятницу') == '2025-08-01'

