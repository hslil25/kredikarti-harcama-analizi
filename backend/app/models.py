"""ORM models for the cached EVDS data.

We store every observation as (series_code, date, value). The catalog
(catalog.py) holds the metadata, so the DB stays a thin, replaceable cache.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import DateTime, Float, String, UniqueConstraint, func
from sqlalchemy import Date as SADate
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Observation(Base):
    """A single data point for a series at a date."""

    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("series_code", "obs_date", name="uq_series_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_code: Mapped[str] = mapped_column(String(64), index=True)
    obs_date: Mapped[date] = mapped_column(SADate, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)


class IngestLog(Base):
    """Records each ingest run so we know how fresh the cache is."""

    __tablename__ = "ingest_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    series_count: Mapped[int] = mapped_column(default=0)
    rows_upserted: Mapped[int] = mapped_column(default=0)
    note: Mapped[str] = mapped_column(String(255), default="")


def init_db() -> None:
    from .db import engine

    Base.metadata.create_all(engine)
