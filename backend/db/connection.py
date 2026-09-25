"""Database connection manager."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from config import settings
from db.models import Base


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

_PATIENT_EXTRA_COLUMNS = {
    "spouse_parent_of": "VARCHAR(200)",
    "contact_phone": "VARCHAR(50)",
    "address": "TEXT",
    "district": "VARCHAR(100)",
    "block": "VARCHAR(100)",
    "health_centre": "VARCHAR(200)",
    "answers": "JSON",
    "saved_at": "TIMESTAMP",
}


def _migrate_schema() -> None:
    """Idempotent ALTER TABLE for pre-existing SQLite files (no Alembic)."""
    insp = inspect(engine)
    if "patients" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("patients")}
    with engine.begin() as conn:
        for col, ddl_type in _PATIENT_EXTRA_COLUMNS.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE patients ADD COLUMN {col} {ddl_type}"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_schema()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
