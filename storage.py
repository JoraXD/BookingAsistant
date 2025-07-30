import os
import sqlite3
from typing import List, Dict

DB_FILE = os.getenv('TRIPS_DB', os.path.join(os.path.dirname(__file__), 'trips.db'))

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            origin TEXT,
            destination TEXT,
            date TEXT,
            transport TEXT,
            status TEXT DEFAULT 'active'
        )
        """
    )
    conn.commit()
    conn.close()

init_db()

def _get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def save_trip(data: Dict) -> int:
    conn = _get_conn()
    with conn:
        cur = conn.execute(
            "INSERT INTO trips (user_id, origin, destination, date, transport, status) VALUES (?, ?, ?, ?, ?, ?)",
            (
                data.get('user_id'),
                data.get('origin'),
                data.get('destination'),
                data.get('date'),
                data.get('transport'),
                data.get('status', 'active'),
            ),
        )
        trip_id = cur.lastrowid
    conn.close()
    return trip_id

def get_last_trips(user_id: int, limit: int = 5) -> List[Dict]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, user_id, origin, destination, date, transport, status FROM trips WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

def cancel_trip(trip_id: int) -> bool:
    conn = _get_conn()
    with conn:
        cur = conn.execute(
            "UPDATE trips SET status='cancelled' WHERE id=? AND status!='cancelled'",
            (trip_id,),
        )
        success = cur.rowcount > 0
    conn.close()
    return success
