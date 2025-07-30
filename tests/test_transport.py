
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'x')
os.environ.setdefault('YANDEX_IAM_TOKEN', 'x')
os.environ.setdefault('YANDEX_FOLDER_ID', 'x')

from parser import parse_transport

def test_plane():
    assert parse_transport('хочу полететь в Москву') == 'plane'

def test_bus():
    assert parse_transport('доедем на басе в Казань') == 'bus'

def test_train():
    assert parse_transport('билеты на поезд до Сочи') == 'train'

def test_default():
    assert parse_transport('нужно в Нижний Новгород') == 'train'
