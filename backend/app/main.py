"""FastAPI app exposing the credit-card / CPI analysis endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import catalog, compute
from .db import get_db
from .models import IngestLog, Observation, init_db

app = FastAPI(title="Türkiye Kredi Kartı Harcama Analizi", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    last = db.execute(
        select(IngestLog).order_by(IngestLog.run_at.desc()).limit(1)
    ).scalar_one_or_none()
    n_obs = db.execute(select(func.count(Observation.id))).scalar_one()
    return {
        "status": "ok",
        "catalog_configured": catalog.is_configured(),
        "observations": n_obs,
        "last_ingest": last.run_at.isoformat() if last else None,
    }


@app.get("/categories")
def categories() -> list[dict]:
    """CC categories the UI offers, with which deflator sources are available."""
    out = []
    for c in catalog.CC_CATEGORIES:
        mp = catalog.MAPPING_BY_KEY.get(c.key)
        out.append({
            "key": c.key,
            "label": c.label,
            "has_tuik": bool(mp and mp.tuik_codes),
            "has_ito": bool(mp and mp.ito_codes),
        })
    return out


@app.get("/real")
def real(
    category: str = Query(..., description="CC category key"),
    source: str = Query("tuik", pattern="^(tuik|ito)$"),
    base: date | None = Query(None, description="Base week for rebasing (YYYY-MM-DD)"),
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Real average ticket for a category, deflated by TÜİK or ITO."""
    try:
        return compute.real_avg_ticket(db, category, source, base, start, end)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/polarization")
def polarization(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Polarization Index: discretionary tx count & avg-ticket ratios vs food."""
    return compute.polarization(db, start, end)
