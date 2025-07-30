import os
import sys
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'x')
os.environ.setdefault('YANDEX_IAM_TOKEN', 'x')
os.environ.setdefault('YANDEX_FOLDER_ID', 'x')

from utils import next_weekday, normalize_date

class FixedDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2025, 7, 28)

def test_next_weekday(monkeypatch):
    monkeypatch.setattr('utils.datetime', FixedDatetime)
    assert next_weekday('пт') == '2025-08-01'
    assert next_weekday('вс') == '2025-08-03'

def test_normalize_date_weekday(monkeypatch):
    monkeypatch.setattr('utils.datetime', FixedDatetime)
    assert normalize_date('в пятницу') == '2025-08-01'

