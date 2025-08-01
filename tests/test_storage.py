import os
import importlib
import tempfile

os.environ['TELEGRAM_BOT_TOKEN'] = os.environ.get('TELEGRAM_BOT_TOKEN', 'x')
os.environ['YANDEX_IAM_TOKEN'] = os.environ.get('YANDEX_IAM_TOKEN', 'x')
os.environ['YANDEX_FOLDER_ID'] = os.environ.get('YANDEX_FOLDER_ID', 'x')

tmp = tempfile.NamedTemporaryFile(delete=False)
os.environ['TRIPS_DB'] = tmp.name
tmp.close()

import storage
importlib.reload(storage)

storage.init_db()


def test_save_and_get_cancel():
    trip_id = storage.save_trip({
        'user_id': 1,
        'origin': 'A',
        'destination': 'B',
        'date': '2025-01-01',
        'transport': 'bus',
    })
    trips = storage.get_last_trips(1)
    assert trips[0]['id'] == trip_id
    assert trips[0]['status'] == 'active'
    assert storage.cancel_trip(trip_id) is True
    trips = storage.get_last_trips(1)
    assert trips[0]['status'] == 'cancelled'
    os.unlink(os.environ['TRIPS_DB'])

