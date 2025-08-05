import os
import sqlite3
from typing import List, Dict

DB_FILE = os.getenv('TRIPS_DB', os.path.join(os.path.dirname(__file__), 'trips.db'))


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            origin TEXT,
            destination TEXT,
            date TEXT,
            transport TEXT,
            status TEXT DEFAULT 'pending'
        )
        """
    )
    # migration from old statuses/structure
    cur.execute("PRAGMA table_info(trips)")
    columns = [row[1] for row in cur.fetchall()]
    if 'status' not in columns:
        cur.execute("ALTER TABLE trips ADD COLUMN status TEXT DEFAULT 'pending'")
    else:
        # migrate old status values if present
        cur.execute("UPDATE trips SET status='pending' WHERE status='active'")
        cur.execute("UPDATE trips SET status='rejected' WHERE status='cancelled'")
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
                data.get('status', 'pending'),
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
            "UPDATE trips SET status='rejected' WHERE id=? AND status!='rejected'",
            (trip_id,),
        )
        success = cur.rowcount > 0
    conn.close()
    return success


def update_trip_status(trip_id: int, status: str) -> bool:
    conn = _get_conn()
    with conn:
        cur = conn.execute("UPDATE trips SET status=? WHERE id=?", (status, trip_id))
        success = cur.rowcount > 0
    conn.close()
    return success


def get_trips_by_status(status: str) -> List[Dict]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, user_id, origin, destination, date, transport, status FROM trips WHERE status=? ORDER BY id",
        (status,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_trip(trip_id: int) -> Dict | None:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, user_id, origin, destination, date, transport, status FROM trips WHERE id=?",
        (trip_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None
