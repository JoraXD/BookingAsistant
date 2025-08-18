import os
import json

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("YANDEX_API_KEY", "x")
os.environ.setdefault("YANDEX_FOLDER_ID", "x")

from bookingassistant.parser import _extract_json


def test_extract_json_first_object():
    text = '{"a":1}\n{"b":2}'
    extracted = _extract_json(text)
    assert json.loads(extracted) == {"a": 1}
