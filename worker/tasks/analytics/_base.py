"""Shared infrastructure for the 35 analytics modules.

Each module file declares a pure function::

    @register(key="A01_revenue_summary",
              analysis_type="revenue",
              required_cols=["total_amount", "order_date"],
              optional_cols=["net_amount", "region", "currency"])
    def run(df: pd.DataFrame) -> dict[str, Any]:
        ...

Registration populates `ANALYTICS_REGISTRY`, which both the standalone runner
(`worker/run_analytics.py`) and the future Celery wrapper (in stage4_upsert)
read to dispatch work.

Pure-function design means every module is testable without Celery/Redis/
Postgres — you just call `run(df)` with a DataFrame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd


# ── Registry ────────────────────────────────────────────────────────────────


@dataclass
class ModuleSpec:
    key: str
    analysis_type: str
    fn: Callable[[pd.DataFrame], dict[str, Any]]
    required_cols: frozenset[str] = field(default_factory=frozenset)
    optional_cols: frozenset[str] = field(default_factory=frozenset)
    description: str = ""

    def can_run(self, available_cols: Iterable[str]) -> tuple[bool, set[str]]:
        """Return (eligible, missing_required_cols)."""
        avail = set(available_cols)
        missing = self.required_cols - avail
        return (not missing), missing


ANALYTICS_REGISTRY: dict[str, ModuleSpec] = {}


def register(
    key: str,
    analysis_type: str,
    required_cols: Iterable[str] | None = None,
    optional_cols: Iterable[str] | None = None,
    description: str = "",
):
    """Decorator: register a `run(df) -> dict` function under `key`.

    Writes to two places so both code paths work:

    1. `ANALYTICS_REGISTRY` (local) — used by `worker/run_analytics.py` CLI.
    2. `schema.MODULES[key].fn` (global) — used by the Celery pipeline
       (`stage5_run_module` looks up the function pointer here).

    If `schema.MODULES` already has an entry for `key` we attach the function
    to it. If it doesn't (e.g. a brand-new module the schema author hasn't
    registered yet), we create a minimal entry so dispatch still works.
    """

    def decorator(fn: Callable[[pd.DataFrame], dict[str, Any]]):
        req = frozenset(required_cols or [])
        opt = frozenset(optional_cols or [])

        # 1. Local registry (CLI runner).
        ANALYTICS_REGISTRY[key] = ModuleSpec(
            key=key,
            analysis_type=analysis_type,
            fn=fn,
            required_cols=req,
            optional_cols=opt,
            description=description,
        )

        # 2. Central schema registry (Celery pipeline).
        try:
            import schema as _schema  # worker/schema.py
            if key in _schema.MODULES:
                _schema.MODULES[key].fn = fn
                _schema.MODULES[key].analysis_type = analysis_type
            else:
                # Module not pre-declared in schema.py — create a minimal
                # AnalyticsModule so the pipeline can still dispatch it.
                _schema.MODULES[key] = _schema.AnalyticsModule(
                    key=key,
                    name=key,
                    name_ar=key,
                    description=description,
                    required_cols=req,
                    optional_cols=opt,
                    series="A",
                    fn=fn,
                    analysis_type=analysis_type,
                )
        except Exception:
            # In contexts where worker/ isn't on sys.path (e.g. some test
            # harnesses), silently skip schema wiring — the local registry
            # is enough for the CLI runner.
            pass

        return fn

    return decorator


# ── Helpers ─────────────────────────────────────────────────────────────────


def has_col(df: pd.DataFrame, col: str) -> bool:
    """True if column exists and contains at least one non-null value."""
    return col in df.columns and df[col].notna().any()


def coerce_numeric(series: pd.Series) -> pd.Series:
    """Strip currency symbols and thousand separators, then `to_numeric`.

    Handles: '$1,234.56', '1.234,56' (best-effort), 'USD 1234', '  $25 '.
    Returns NaN for anything unparseable.
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = (
        series.astype(str)
        .str.replace(r"[^\d.,\-]", "", regex=True)  # drop symbols, letters, currency
        .str.replace(",", "", regex=False)          # treat , as thousand sep
    )
    return pd.to_numeric(cleaned, errors="coerce")


def coerce_date(series: pd.Series) -> pd.Series:
    """Parse a column that may contain mixed date formats."""
    return pd.to_datetime(series, errors="coerce", format="mixed")


def sanitize_json(obj: Any) -> Any:
    """Make a value JSON-serialisable for the analysis_results_cache."""
    if obj is None:
        return None
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float, Decimal)):
        return round(float(obj), 4)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, pd.Period):
        return str(obj)
    return obj


def to_period_str(d, freq: str = "M") -> str:
    return pd.Period(d, freq=freq).strftime("%Y-%m" if freq == "M" else "%Y")
