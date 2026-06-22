"""Thin wrapper around the official `evds` package.

Returns tidy long-format DataFrames: columns [series_code, obs_date, value].
EVDS returns wide data (one column per series) with a Turkish-formatted
date column, so we melt + parse here so the rest of the app never sees the
raw shape.
"""
from __future__ import annotations

import pandas as pd
from evds import evdsAPI

from .config import get_settings


# EVDS date format used by both request params and the returned column.
_DATE_FORMATS = ("%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%Y-%m")


def _to_evds_date(d: pd.Timestamp | str) -> str:
    ts = pd.Timestamp(d)
    return ts.strftime("%d-%m-%Y")


def _parse_dates(raw: pd.Series) -> pd.Series:
    for fmt in _DATE_FORMATS:
        parsed = pd.to_datetime(raw, format=fmt, errors="coerce")
        if parsed.notna().mean() > 0.8:
            return parsed
    # last resort: let pandas infer
    return pd.to_datetime(raw, errors="coerce", dayfirst=True)


class EvdsClient:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or get_settings().evds_api_key
        if not key:
            raise RuntimeError("EVDS_API_KEY is not set (see backend/.env.example)")
        # legacySSL=True (the package default) builds a custom SSL context that
        # skips the certifi CA bundle and fails with a false "self-signed
        # certificate" error on modern Python. The host serves a valid cert, so
        # we use the standard TLS path instead.
        self._api = evdsAPI(key, legacySSL=False)

    def get_long(
        self,
        codes: list[str],
        start: str,
        end: str,
        frequency: int | None = None,
    ) -> pd.DataFrame:
        """Fetch series and return long format [series_code, obs_date, value].

        start/end accept ISO ('2019-01-01') or any pandas-parseable date;
        they are converted to EVDS' DD-MM-YYYY.
        """
        if not codes:
            return pd.DataFrame(columns=["series_code", "obs_date", "value"])

        kwargs: dict = {
            "startdate": _to_evds_date(start),
            "enddate": _to_evds_date(end),
        }
        if frequency is not None:
            kwargs["frequency"] = frequency

        wide = self._api.get_data(codes, **kwargs)
        if wide is None or wide.empty:
            return pd.DataFrame(columns=["series_code", "obs_date", "value"])

        # EVDS adds a 'Tarih' (date) column and often a 'UNIXTIME' helper col.
        date_col = next(
            (c for c in wide.columns if c.lower() in ("tarih", "date")),
            wide.columns[0],
        )
        value_cols = [
            c for c in wide.columns
            if c != date_col and c.upper() not in ("UNIXTIME", "YEARWEEK")
        ]

        long = wide.melt(
            id_vars=[date_col],
            value_vars=value_cols,
            var_name="series_code",
            value_name="value",
        ).copy()
        long["obs_date"] = _parse_dates(long[date_col]).dt.date
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        # EVDS replaces the dots in codes with underscores in column names.
        code_fix = {c.replace(".", "_"): c for c in codes}
        long["series_code"] = long["series_code"].map(lambda c: code_fix.get(c, c))
        return long[["series_code", "obs_date", "value"]].dropna(subset=["obs_date"])
