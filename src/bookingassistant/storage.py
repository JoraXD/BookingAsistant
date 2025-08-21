"""Простой слой хранения поездок на SQLite с использованием SQLAlchemy 2.x."""

from __future__ import annotations

import os
from typing import Dict, List

from sqlalchemy import Column, Integer, String, create_engine, inspect, select, update
from sqlalchemy.orm import Session, declarative_base


DB_FILE = os.getenv("TRIPS_DB", os.path.join(os.path.dirname(__file__), "trips.db"))

engine = create_engine(f"sqlite:///{DB_FILE}", future=True)
Base = declarative_base()


class Trip(Base):
    """ORM-модель поездки."""

    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    origin = Column(String)
    destination = Column(String)
    date = Column(String)
    transport = Column(String)
    status = Column(String, default="pending", server_default="pending")

    def to_dict(self) -> Dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def init_db() -> None:
    """Инициализировать базу данных и выполнить миграции."""
    engine.dispose()
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        inspector = inspect(conn)
        columns = [col["name"] for col in inspector.get_columns("trips")]
        if "status" not in columns:
            conn.exec_driver_sql("ALTER TABLE trips ADD COLUMN status TEXT DEFAULT 'pending'")
        else:
            conn.exec_driver_sql("UPDATE trips SET status='pending' WHERE status='active'")
            conn.exec_driver_sql("UPDATE trips SET status='rejected' WHERE status='cancelled'")


init_db()


def save_trip(data: Dict) -> int:
    """Сохранить поездку и вернуть её ID."""

    with Session(engine) as session:
        trip = Trip(
            user_id=data.get("user_id"),
            origin=data.get("origin"),
            destination=data.get("destination"),
            date=data.get("date"),
            transport=data.get("transport"),
            status=data.get("status", "pending"),
        )
        session.add(trip)
        session.commit()
        session.refresh(trip)
        return trip.id


def get_last_trips(user_id: int, limit: int = 5) -> List[Dict]:
    """Получить последние поездки пользователя."""

    with Session(engine) as session:
        stmt = (
            select(Trip)
            .where(Trip.user_id == user_id)
            .order_by(Trip.id.desc())
            .limit(limit)
        )
        trips = session.execute(stmt).scalars().all()
        return [t.to_dict() for t in trips]


def cancel_trip(trip_id: int) -> bool:
    """Отменить поездку по её ID."""

    with Session(engine) as session:
        stmt = (
            update(Trip)
            .where(Trip.id == trip_id, Trip.status != "rejected")
            .values(status="rejected")
        )
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0


def update_trip_status(trip_id: int, status: str) -> bool:
    """Обновить статус поездки."""

    with Session(engine) as session:
        stmt = update(Trip).where(Trip.id == trip_id).values(status=status)
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0


def get_trips_by_status(status: str) -> List[Dict]:
    """Получить все поездки с указанным статусом."""

    with Session(engine) as session:
        stmt = select(Trip).where(Trip.status == status).order_by(Trip.id)
        trips = session.execute(stmt).scalars().all()
        return [t.to_dict() for t in trips]


def get_trip(trip_id: int) -> Dict | None:
    """Вернуть данные одной поездки или ``None``."""

    with Session(engine) as session:
        trip = session.get(Trip, trip_id)
        return trip.to_dict() if trip else None


