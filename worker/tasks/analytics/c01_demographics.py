"""C01 — Customer Demographics.

Distribution of gender / age / age-bracket from any combination of those
columns. Eligible if at least one of (gender, age, birth_date) is present.

Required columns:  (none — dynamic OR-condition handled by schema.check_eligibility)
Optional columns:  gender, age, birth_date, customer_id, total_amount
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


AGE_BUCKETS = [
    (0,  18,  "under-18"),
    (18, 25,  "18-24"),
    (25, 35,  "25-34"),
    (35, 45,  "35-44"),
    (45, 55,  "45-54"),
    (55, 65,  "55-64"),
    (65, 200, "65+"),
]


def _age_from_birth(s: pd.Series) -> pd.Series:
    bd = coerce_date(s)
    today = pd.Timestamp(datetime.utcnow().date())
    years = (today - bd).dt.days / 365.25
    return years.where(years.between(0, 110))


def _bucketize(ages: pd.Series) -> list[dict[str, Any]]:
    n = int(ages.notna().sum())
    out = []
    for lo, hi, label in AGE_BUCKETS:
        mask = (ages >= lo) & (ages < hi)
        cnt = int(mask.sum())
        out.append({
            "bucket": label,
            "count":  cnt,
            "pct":    round(cnt / n * 100, 2) if n else 0.0,
        })
    return out


@register(
    key="C01_demographics",
    analysis_type="customer",
    required_cols=[],
    optional_cols=["gender", "age", "birth_date", "customer_id", "total_amount"],
    description="Age + gender demographic distribution.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    avail = {c: has_col(df, c) for c in ("gender", "age", "birth_date", "customer_id", "total_amount")}
    if not any(avail[c] for c in ("gender", "age", "birth_date")):
        return _empty("dataset has none of gender / age / birth_date — module skipped")

    # Dedupe to one row per customer where possible (so age/gender aren't counted per-order).
    if avail["customer_id"]:
        df["customer_id"] = df["customer_id"].astype(str)
        df = df.drop_duplicates("customer_id", keep="first")

    n_customers = int(len(df))

    # ── Age ─────────────────────────────────────────────────────────────────
    age_series = None
    age_source = None
    if avail["age"]:
        age_series = coerce_numeric(df["age"])
        age_series = age_series.where(age_series.between(0, 110))
        age_source = "age column"
    elif avail["birth_date"]:
        age_series = _age_from_birth(df["birth_date"])
        age_source = "computed from birth_date"

    age_distribution = _bucketize(age_series) if age_series is not None else None
    age_stats = None
    if age_series is not None and age_series.notna().any():
        age_stats = {
            "n_with_age":  int(age_series.notna().sum()),
            "avg_age":     round(float(age_series.mean()), 2),
            "median_age":  round(float(age_series.median()), 2),
            "p10_age":     round(float(age_series.quantile(0.10)), 2),
            "p90_age":     round(float(age_series.quantile(0.90)), 2),
            "source":      age_source,
        }

    # ── Gender ──────────────────────────────────────────────────────────────
    gender_distribution = None
    if avail["gender"]:
        gn = df["gender"].astype(str).str.strip().str.lower()
        gn = gn.replace({"m": "male", "f": "female", "": None})
        gn = gn[gn.notna()]
        if not gn.empty:
            counts = gn.value_counts()
            gender_distribution = [
                {
                    "gender": str(g),
                    "count":  int(c),
                    "pct":    round(c / len(gn) * 100, 2),
                }
                for g, c in counts.items()
            ]

    # ── Optional revenue per age bucket ─────────────────────────────────────
    revenue_by_age = None
    if age_series is not None and avail["total_amount"]:
        amt = coerce_numeric(df["total_amount"]).fillna(0)
        tmp = pd.DataFrame({"age": age_series, "rev": amt}).dropna(subset=["age"])
        rows = []
        for lo, hi, label in AGE_BUCKETS:
            mask = (tmp["age"] >= lo) & (tmp["age"] < hi)
            rev = float(tmp.loc[mask, "rev"].sum())
            rows.append({
                "bucket":  label,
                "revenue": round(rev, 2),
            })
        revenue_by_age = rows

    return {
        "summary": {
            "n_customers": n_customers,
            "has_gender":     bool(avail["gender"]),
            "has_age":        age_series is not None,
            "age_source":     age_source,
        },
        "age_stats":            age_stats,
        "age_distribution":     age_distribution,
        "gender_distribution":  gender_distribution,
        "revenue_by_age_bucket": revenue_by_age,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_customers": 0, "has_gender": False,
            "has_age": False, "age_source": None,
        },
        "age_stats": None, "age_distribution": None,
        "gender_distribution": None, "revenue_by_age_bucket": None,
        "warning": warning,
    }
