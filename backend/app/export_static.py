"""Export all API responses as static JSON for a serverless (GitHub Pages)
deploy. Run: python -m app.export_static

Writes into frontend/public/data/ :
  categories.json
  health.json
  real/<cc_key>__<source>.json   (source = tuik, and ito where mapped)

The frontend reads these files directly; base-period rebasing is done
client-side (it only rescales the real line, which is derivable from the
per-point nominal_avg_ticket and cpi).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import catalog, compute
from .db import SessionLocal

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def main() -> None:
    (OUT / "real").mkdir(parents=True, exist_ok=True)

    cats = []
    for c in catalog.CC_CATEGORIES:
        mp = catalog.MAPPING_BY_KEY.get(c.key)
        cats.append({
            "key": c.key,
            "label": c.label,
            "has_tuik": bool(mp and mp.tuik_codes),
            "has_ito": bool(mp and mp.ito_codes),
        })
    _write(OUT / "categories.json", cats)
    _write(OUT / "health.json",
           {"status": "ok", "catalog_configured": catalog.is_configured()})

    n = 0
    with SessionLocal() as db:
        for c in catalog.CC_CATEGORIES:
            mp = catalog.MAPPING_BY_KEY.get(c.key)
            sources = ["tuik"] + (["ito"] if mp and mp.ito_codes else [])
            for s in sources:
                data = compute.real_avg_ticket(db, c.key, s)
                _write(OUT / "real" / f"{c.key}__{s}.json", data)
                n += 1
    print(f"exported {n} real files + categories/health to {OUT}")


if __name__ == "__main__":
    main()
