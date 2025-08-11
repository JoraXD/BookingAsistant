"""Простой слой хранения поездок на SQLite, реализованный на SQLAlchemy 2.x."""

from __future__ import annotations

import os
from typing import Dict, List

from sqlalchemy import Engine, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


# Путь к файлу базы данных задаётся через переменную окружения
DB_FILE = os.getenv(
    "TRIPS_DB", os.path.join(os.path.dirname(__file__), "trips.db")
)

# Движок создаётся лениво в ``init_db``
engine: Engine | None = None


class Base(DeclarativeBase):
    """Базовый класс декларативных моделей."""


class Trip(Base):
    """ORM-модель поездки."""

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int]
    origin: Mapped[str]
    destination: Mapped[str]
    date: Mapped[str]
    transport: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending")


def init_db() -> None:
    """Инициализировать базу данных и выполнить миграции."""
    global engine, DB_FILE
    DB_FILE = os.getenv(
        "TRIPS_DB", os.path.join(os.path.dirname(__file__), "trips.db")
    )
    engine = create_engine(f"sqlite:///{DB_FILE}", future=True)

    # Создаём таблицы, если их ещё нет
    Base.metadata.create_all(engine)

    # Простейшая миграция из старой схемы
    with engine.begin() as conn:
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(trips)")]
        if "status" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE trips ADD COLUMN status TEXT DEFAULT 'pending'"
            )
        else:
            conn.exec_driver_sql(
                "UPDATE trips SET status='pending' WHERE status='active'"
            )
            conn.exec_driver_sql(
                "UPDATE trips SET status='rejected' WHERE status='cancelled'"
            )



def _get_engine() -> Engine:
    """Вернуть текущий движок, инициализируя при необходимости."""
    if engine is None:
        init_db()
    return engine


def _trip_to_dict(trip: Trip) -> Dict:
    return {
        "id": trip.id,
        "user_id": trip.user_id,
        "origin": trip.origin,
        "destination": trip.destination,
        "date": trip.date,
        "transport": trip.transport,
        "status": trip.status,
    }


def save_trip(data: Dict) -> int:
    """Сохранить поездку и вернуть её ID."""
    trip = Trip(
        user_id=data.get("user_id"),
        origin=data.get("origin"),
        destination=data.get("destination"),
        date=data.get("date"),
        transport=data.get("transport"),
        status=data.get("status", "pending"),
    )
    with Session(_get_engine()) as session:
        session.add(trip)
        session.commit()
        session.refresh(trip)
        return trip.id


def get_last_trips(user_id: int, limit: int = 5) -> List[Dict]:
    """Получить последние поездки пользователя."""
    stmt = (
        select(Trip)
        .where(Trip.user_id == user_id)
        .order_by(Trip.id.desc())
        .limit(limit)
    )
    with Session(_get_engine()) as session:
        trips = session.execute(stmt).scalars().all()
        return [_trip_to_dict(t) for t in trips]


def cancel_trip(trip_id: int) -> bool:
    """Отменить поездку по её ID."""
    stmt = (
        update(Trip)
        .where(Trip.id == trip_id, Trip.status != "rejected")
        .values(status="rejected")
    )
    with Session(_get_engine()) as session:
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0


def update_trip_status(trip_id: int, status: str) -> bool:
    """Обновить статус поездки."""
    stmt = update(Trip).where(Trip.id == trip_id).values(status=status)
    with Session(_get_engine()) as session:
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0


def get_trips_by_status(status: str) -> List[Dict]:
    """Получить все поездки с указанным статусом."""
    stmt = select(Trip).where(Trip.status == status).order_by(Trip.id)
    with Session(_get_engine()) as session:
        trips = session.execute(stmt).scalars().all()
        return [_trip_to_dict(t) for t in trips]


def get_trip(trip_id: int) -> Dict | None:
    """Вернуть данные одной поездки или ``None``."""
    with Session(_get_engine()) as session:
        trip = session.get(Trip, trip_id)
        return _trip_to_dict(trip) if trip else None

