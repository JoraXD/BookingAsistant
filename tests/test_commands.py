import os
import importlib

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'x')
os.environ.setdefault('YANDEX_IAM_TOKEN', 'x')
os.environ.setdefault('YANDEX_FOLDER_ID', 'x')

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import parser
importlib.reload(parser)


def test_show_command():
    data = parser.parse_history_request("покажи последние 3 поездки")
    assert data['action'] == 'show'
    assert data['limit'] == 3


def test_cancel_command():
    data = parser.parse_history_request("пожалуйста, отмени поездку в Москву")
    assert data['action'] == 'cancel'
    assert data['destination'].lower() == 'москву' or data['destination'].lower() == 'москва'
