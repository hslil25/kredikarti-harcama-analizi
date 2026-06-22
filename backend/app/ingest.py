"""Fetch EVDS series and upsert them into the local cache.

Run manually:   python -m app.ingest
Or call run_ingest() from a scheduler (cron / APScheduler) later.

We fetch weekly and monthly series in separate calls because they need
different `frequency` values.
"""
from __future__ import annotations

import sys
from datetime import date

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from . import catalog
from .catalog import Freq, SeriesKind
from .db import SessionLocal
from .evds_client import EvdsClient
from .models import IngestLog, Observation, init_db

# How far back to pull on a full refresh.
DEFAULT_START = "2014-01-01"

_WEEKLY_KINDS = {SeriesKind.CC_AMOUNT, SeriesKind.CC_COUNT}


def _codes_by_freq() -> dict[Freq, list[str]]:
    out: dict[Freq, list[str]] = {Freq.WEEKLY: [], Freq.MONTHLY: []}
    for s in catalog.SERIES:
        out[s.freq].append(s.code)
    return out


def _upsert(db, rows: list[dict], chunk: int = 500) -> int:
    # SQLite caps bound variables per statement, so insert in chunks
    # (3 columns -> chunk*3 variables).
    total = 0
    for i in range(0, len(rows), chunk):
        batch = rows[i : i + chunk]
        stmt = sqlite_insert(Observation).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_code", "obs_date"],
            set_={"value": stmt.excluded.value},
        )
        db.execute(stmt)
        total += len(batch)
    return total


def run_ingest(start: str = DEFAULT_START, end: str | None = None) -> int:
    end = end or date.today().isoformat()
    if not catalog.is_configured():
        raise RuntimeError(
            "catalog.py still has PLACEHOLDER codes — add real EVDS series first."
        )

    init_db()
    client = EvdsClient()
    total = 0

    with SessionLocal() as db:
        for freq, codes in _codes_by_freq().items():
            if not codes:
                continue
            long = client.get_long(codes, start=start, end=end, frequency=int(freq))
            rows = [
                {
                    "series_code": r.series_code,
                    "obs_date": r.obs_date,
                    "value": None if r.value != r.value else float(r.value),  # NaN check
                }
                for r in long.itertuples(index=False)
            ]
            total += _upsert(db, rows)

        db.add(IngestLog(series_count=len(catalog.SERIES), rows_upserted=total,
                         note=f"{start}..{end}"))
        db.commit()

    return total


if __name__ == "__main__":
    try:
        n = run_ingest()
        print(f"Ingest complete: {n} rows upserted.")
    except Exception as exc:  # noqa: BLE001
        print(f"Ingest failed: {exc}", file=sys.stderr)
        sys.exit(1)
