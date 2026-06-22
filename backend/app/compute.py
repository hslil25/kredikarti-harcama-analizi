"""Analytics: average ticket, CPI rebasing/interpolation, real values.

Everything is computed from the cached Observation table. The headline
metric is the REAL AVERAGE TICKET:

    avg_ticket(t)      = cc_amount(t) / cc_count(t)
    real_avg_ticket(t) = avg_ticket(t) * CPI(base) / CPI(t)

CPI is monthly, CC data is weekly, so the chosen CPI series is linearly
interpolated to the weekly index before deflating.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import catalog
from .models import Observation

# EVDS reports TP.KKHARTUT amounts in THOUSAND TL; scale to actual TL so the
# average ticket is a real per-transaction lira figure.
AMOUNT_SCALE = 1000

# Weekly observations per year, for year-over-year change.
_WEEKS_PER_YEAR = 52


def _series(db: Session, code: str) -> pd.Series:
    rows = db.execute(
        select(Observation.obs_date, Observation.value)
        .where(Observation.series_code == code)
        .order_by(Observation.obs_date)
    ).all()
    if not rows:
        return pd.Series(dtype="float64")
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.Series([r[1] for r in rows], index=idx, name=code).sort_index()


def _composite_cpi(db: Session, codes: list[str], weights: list[float]) -> pd.Series:
    """Weighted average of one or more CPI series (weights normalised)."""
    parts = [(_series(db, c), w) for c, w in zip(codes, weights) if codes]
    parts = [(s, w) for s, w in parts if not s.empty]
    if not parts:
        return pd.Series(dtype="float64")
    frame = pd.concat([s for s, _ in parts], axis=1)
    w = pd.Series([w for _, w in parts], index=frame.columns)
    w = w / w.sum()
    return (frame * w).sum(axis=1, min_count=1)


def _components(
    db: Session,
    codes: list[str],
    weights: list[float],
    target_index: pd.DatetimeIndex,
) -> list[dict]:
    """Per-component CPI: weekly index + YoY + normalised weight + label."""
    total = sum(weights) or 1.0
    out: list[dict] = []
    for code, w in zip(codes, weights):
        comp_key, comp_label = catalog.component_meta(code)
        weekly = _interp_to_index(_series(db, code), target_index)
        out.append({
            "key": comp_key,
            "coicop": comp_key,
            "code": code,
            "label": comp_label,
            "weight": round(w / total, 4),
            "weekly": weekly,
            "yoy": weekly.pct_change(_WEEKS_PER_YEAR) * 100,
        })
    return out


def _interp_to_index(monthly: pd.Series, target_index: pd.DatetimeIndex) -> pd.Series:
    """Linearly interpolate a monthly series onto an arbitrary (weekly) index."""
    if monthly.empty:
        return pd.Series(index=target_index, dtype="float64")
    union = monthly.index.union(target_index)
    interp = monthly.reindex(union).interpolate(method="time").reindex(target_index)
    return interp


def _rebase(cpi: pd.Series, base: date | None) -> tuple[pd.Series, pd.Timestamp]:
    """Return CPI(base)/CPI(t) factors and the actual base timestamp used."""
    if cpi.dropna().empty:
        return cpi, pd.NaT
    if base is None:
        base_ts = cpi.dropna().index.max()
    else:
        # nearest available observation to the requested base date
        base_ts = cpi.dropna().index[cpi.dropna().index.get_indexer(
            [pd.Timestamp(base)], method="nearest")[0]]
    base_val = cpi.loc[base_ts]
    return base_val / cpi, base_ts


def real_avg_ticket(
    db: Session,
    cc_key: str,
    source: str = "tuik",            # "tuik" | "ito"
    base: date | None = None,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    cc = catalog.CC_BY_KEY.get(cc_key)
    mp = catalog.MAPPING_BY_KEY.get(cc_key)
    if cc is None or mp is None:
        raise KeyError(f"unknown cc category: {cc_key}")

    amount = _series(db, cc.amount_code) * AMOUNT_SCALE
    count = _series(db, cc.count_code)
    avg_ticket = (amount / count).replace([float("inf"), float("-inf")], pd.NA).dropna()

    if source == "ito":
        cpi_codes, cpi_w = mp.ito_codes, mp.weights_ito
    else:
        cpi_codes, cpi_w = mp.tuik_codes, mp.weights_tuik

    cpi_monthly = _composite_cpi(db, cpi_codes, cpi_w)
    cpi_weekly = _interp_to_index(cpi_monthly, avg_ticket.index)
    factor, base_ts = _rebase(cpi_weekly, base)

    real = (avg_ticket * factor).dropna()

    # Year-over-year CPI inflation (%) on the weekly index.
    cpi_yoy = cpi_weekly.pct_change(_WEEKS_PER_YEAR) * 100

    # Per-component breakdown (normalised weights + each component's YoY).
    comps = _components(db, cpi_codes, cpi_w, avg_ticket.index)

    # Polarization vs basic goods (market): ratios over time. Scale- and
    # inflation-free (both sides nominal). Meaningless for the basic category
    # itself (ratio to itself = 1), so the frontend hides it there.
    basic = catalog.CC_BY_KEY[BASIC_KEY]
    m_count = _series(db, basic.count_code)
    m_ticket = ((_series(db, basic.amount_code) * AMOUNT_SCALE) / m_count).replace(
        list(_INF), pd.NA)
    pi_count = count / m_count
    pi_ticket = (amount / count) / m_ticket

    out = pd.DataFrame({
        "nominal_avg_ticket": avg_ticket,
        "cpi": cpi_weekly,
        "real_avg_ticket": real,
        "cpi_yoy": cpi_yoy,
        "pi_count": pi_count,
        "pi_ticket": pi_ticket,
    })
    for c in comps:
        out[f"{c['key']}_yoy"] = c["yoy"]
    if start:
        out = out[out.index >= pd.Timestamp(start)]
    if end:
        out = out[out.index <= pd.Timestamp(end)]

    comp_yoy_cols = [f"{c['key']}_yoy" for c in comps]

    return {
        "cc_key": cc_key,
        "cc_label": cc.label,
        "source": source,
        "base_date": None if pd.isna(base_ts) else base_ts.date().isoformat(),
        "is_basic": cc_key == BASIC_KEY,
        "basic_label": basic.label,
        "summary": _summary(out),
        "components": [
            {"key": c["key"], "coicop": c["coicop"], "label": c["label"],
             "weight": c["weight"]}
            for c in comps
        ],
        "points": [
            {
                "date": ts.date().isoformat(),
                "nominal_avg_ticket": _num(row.nominal_avg_ticket),
                "real_avg_ticket": _num(row.real_avg_ticket),
                "cpi": _num(row.cpi),
                "cpi_yoy": _num(row.cpi_yoy),
                "pi_count": _num(row.pi_count),
                "pi_ticket": _num(row.pi_ticket),
                **{col: _num(row[col]) for col in comp_yoy_cols},
            }
            for ts, row in out.iterrows()
        ],
    }


def _summary(out: pd.DataFrame) -> dict:
    """Headline stats over the (filtered) window shown on the charts."""
    def change(col: str) -> float | None:
        s = out[col].dropna()
        if len(s) < 2 or s.iloc[0] == 0:
            return None
        return round((s.iloc[-1] / s.iloc[0] - 1) * 100, 2)

    period = out.index
    yoy = out["cpi_yoy"].dropna()
    return {
        "period_start": period.min().date().isoformat() if len(period) else None,
        "period_end": period.max().date().isoformat() if len(period) else None,
        "nominal_change_pct": change("nominal_avg_ticket"),
        "real_change_pct": change("real_avg_ticket"),
        "cumulative_inflation_pct": change("cpi"),
        "latest_cpi_yoy": round(float(yoy.iloc[-1]), 2) if len(yoy) else None,
    }


def _num(v) -> float | None:
    return None if pd.isna(v) else round(float(v), 4)


def _sig(v, sig: int = 6) -> float | None:
    """Round to `sig` significant figures (PI values are very small in absolute
    terms, so fixed-decimal rounding would collapse them to 0)."""
    if pd.isna(v):
        return None
    if v == 0:
        return 0.0
    from math import floor, log10
    return round(float(v), -int(floor(log10(abs(v)))) + (sig - 1))


# ===========================================================================
# Polarization Index
# ===========================================================================
#
# Two ratio time-series per discretionary sector, both measured against the
# basic-goods baseline (supermarket / groceries). Being ratios, they need no
# population (scale cancels) and no inflation adjustment (both sides nominal,
# so aggregate price level cancels):
#
#   PI_count_sector(t)  = transaction_count_sector(t) / transaction_count_food(t)
#   PI_ticket_sector(t) = avg_ticket_sector(t) / avg_ticket_food(t)
#                         where avg_ticket = amount / count
#
#   PI_count_combined(t)  = sum of PI_count_sector(t)
#   PI_ticket_combined(t) = sum of PI_ticket_sector(t)
#
# Discretionary sectors -> CC category keys.
DISCRETIONARY_SECTORS: dict[str, str] = {
    "clothing": "kt9",          # Giyim ve Aksesuar
    "travel": "kt20",           # Seyahat Acenteleri/Taşımacılık
    "direct_marketing": "kt6",  # Doğrudan Pazarlama
    "services": "kt11",         # Hizmet Sektörleri
}

# Basic-goods baseline ("temel ürünler / temel sektör").
BASIC_KEY = "kt16"              # Market ve Alışveriş Merkezleri

_INF = (float("inf"), float("-inf"))


def polarization_index(
    df: pd.DataFrame,
    sectors: list[str] | None = None,
) -> pd.DataFrame:
    """Compute the Polarization Index from an assembled dataframe.

    `df` is indexed by date and must contain, for each sector AND for "food":
      - ``count_<name>``  : transaction count
      - ``amount_<name>`` : spending amount
    where ``<name>`` is each sector plus ``food`` (the basic-goods baseline).

    Returns a dataframe indexed by date with, per sector:
      - ``PI_count_<sector>``  = count_<sector> / count_food
      - ``PI_ticket_<sector>`` = (amount/count)_<sector> / (amount/count)_food
    plus ``PI_count_combined`` and ``PI_ticket_combined`` (row-wise sums).
    """
    sectors = sectors or list(DISCRETIONARY_SECTORS)
    count_food = df["count_food"].replace(0, pd.NA)
    ticket_food = (df["amount_food"] / count_food).replace(_INF, pd.NA)

    out = pd.DataFrame(index=df.index)
    for s in sectors:
        count_s = df[f"count_{s}"]
        ticket_s = (df[f"amount_{s}"] / count_s).replace(_INF, pd.NA)
        out[f"PI_count_{s}"] = count_s / count_food
        out[f"PI_ticket_{s}"] = ticket_s / ticket_food

    out["PI_count_combined"] = out[[f"PI_count_{s}" for s in sectors]].sum(
        axis=1, min_count=1)
    out["PI_ticket_combined"] = out[[f"PI_ticket_{s}" for s in sectors]].sum(
        axis=1, min_count=1)
    return out


def build_polarization_input(
    db: Session,
    sectors: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Assemble the dataframe consumed by :func:`polarization_index`.

    Pulls transaction count + amount for each sector and for the basic-goods
    baseline (``food``).
    """
    sectors = sectors or DISCRETIONARY_SECTORS
    names = {**sectors, "food": BASIC_KEY}
    frames: dict[str, pd.Series] = {}
    for name, cc_key in names.items():
        cc = catalog.CC_BY_KEY[cc_key]
        frames[f"count_{name}"] = _series(db, cc.count_code)
        frames[f"amount_{name}"] = _series(db, cc.amount_code)
    return pd.DataFrame(frames).sort_index()


def polarization(
    db: Session,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """JSON-ready Polarization Index over the cached data."""
    pi = polarization_index(build_polarization_input(db))
    if start:
        pi = pi[pi.index >= pd.Timestamp(start)]
    if end:
        pi = pi[pi.index <= pd.Timestamp(end)]

    cols = list(pi.columns)
    return {
        "sectors": list(DISCRETIONARY_SECTORS),
        "basic": BASIC_KEY,
        "points": [
            {"date": ts.date().isoformat(), **{c: _num(row[c]) for c in cols}}
            for ts, row in pi.iterrows()
        ],
    }
