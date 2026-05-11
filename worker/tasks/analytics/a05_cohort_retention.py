"""A05 — Cohort Retention Analysis.

Bins customers into monthly acquisition cohorts (the month of their first
purchase) and tracks what % of each cohort returns N months later. The output
is the classic triangular cohort heatmap retention analysts read every Monday.

How retention is computed
-------------------------
For each customer, `cohort = first_order_date.to_period('M')`. For every order
they place, `month_offset = (order_month - cohort_month).n` (months elapsed).
Per (cohort, offset) we count *distinct* customers active and divide by
cohort size.

Two important nuances:
- Month 0 retention is always 100% by definition (the cohort is defined by
  having ordered that month). We still emit it for visualization completeness.
- Later cohorts have shorter observation windows. A cohort acquired in the
  last month of the dataset has no future data — its row will have `null`
  for months it can't observe yet (avoids confusing 0% with "unobserved").

Required columns:  customer_id, order_date
Optional columns:  total_amount, net_amount  (for revenue retention)

Output schema::

    {
      "summary": {
        "n_cohorts":         int,
        "n_customers":       int,
        "first_cohort":      "YYYY-MM",
        "last_cohort":       "YYYY-MM",
        "max_month_offset":  int,
        "avg_retention_m1":  float,
        "avg_retention_m3":  float,
        "avg_retention_m6":  float,
        "avg_retention_m12": float
      },
      "cohort_matrix": [
        {
          "cohort": "YYYY-MM", "size": int,
          "retention": [
            {"month_offset": 0,  "active": int, "rate": float|null},
            {"month_offset": 1,  "active": int, "rate": float|null},
            ...
          ]
        }
      ],
      "avg_retention_curve": [
        {"month_offset": 0, "cohorts_observed": int, "rate": float}
      ],
      "best_cohort_m3":  {"cohort": "YYYY-MM", "size": int, "rate": float},
      "worst_cohort_m3": {...},
      "warning": str | None
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, has_col, register


MAX_MONTH_OFFSET = 24  # cap to keep payload bounded; 2-year retention is plenty


@register(
    key="A05_cohort_retention",
    analysis_type="customer",
    required_cols=["customer_id", "order_date"],
    optional_cols=["total_amount", "net_amount"],
    description="Acquisition cohort retention heatmap with avg retention curves.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df = df.dropna(subset=["customer_id", "order_date"])
    df["customer_id"] = df["customer_id"].astype(str)

    if df.empty or df["customer_id"].nunique() == 0:
        return {
            "summary": {"n_cohorts": 0, "n_customers": 0,
                        "first_cohort": None, "last_cohort": None,
                        "max_month_offset": 0,
                        "avg_retention_m1": 0.0, "avg_retention_m3": 0.0,
                        "avg_retention_m6": 0.0, "avg_retention_m12": 0.0},
            "cohort_matrix": [], "avg_retention_curve": [],
            "best_cohort_m3": None, "worst_cohort_m3": None,
            "warning": "no data after coercion",
        }

    # All cohort math uses int (year*12 + month). Period subtraction is
    # dtype-fragile across pandas versions; ints are not. We format back to
    # "YYYY-MM" strings only at output time.
    df["order_month_int"] = df["order_date"].dt.year * 12 + df["order_date"].dt.month
    first_orders = df.groupby("customer_id")["order_month_int"].min().rename("cohort")
    df = df.join(first_orders, on="customer_id")
    df["month_offset"] = (df["order_month_int"] - df["cohort"]).astype(int)
    df = df[(df["month_offset"] >= 0) & (df["month_offset"] <= MAX_MONTH_OFFSET)]

    # Cohort sizes (distinct customers).
    cohort_sizes = (
        df.drop_duplicates(subset="customer_id")
          .groupby("cohort")["customer_id"].nunique()
          .sort_index()
    )

    # Activity matrix: distinct customers per (cohort, month_offset).
    active = (
        df.groupby(["cohort", "month_offset"])["customer_id"].nunique().unstack("month_offset")
    )
    # Ensure every offset column 0..max exists, sorted.
    max_offset = int(df["month_offset"].max())
    full_offsets = list(range(0, max_offset + 1))
    # `unstack` produces NaN for missing (cohort, offset) cells; reindex
    # only fills *new* columns, so we need fillna() before the int cast.
    active = active.reindex(columns=full_offsets, fill_value=0).fillna(0).sort_index().astype(int)

    # ── "Observable" mask ───────────────────────────────────────────────────
    # A cohort acquired in month C can only observe offsets up to
    # (last_period - C). Beyond that we emit None instead of 0% so the
    # heatmap doesn't lie about late cohorts looking like total churn.
    last_period_int = int(df["order_month_int"].max())
    cohort_max_obs: dict[int, int] = {
        int(c): last_period_int - int(c) for c in active.index
    }

    def _fmt_cohort(n: int) -> str:
        """Convert year*12+month back to 'YYYY-MM'."""
        n = int(n)
        year, month = divmod(n - 1, 12)
        return f"{year:04d}-{month + 1:02d}"

    # ── Build cohort_matrix ─────────────────────────────────────────────────
    matrix_out: list[dict[str, Any]] = []
    for cohort, row in active.iterrows():
        cohort_int = int(cohort)
        size = int(cohort_sizes.loc[cohort_int])
        max_obs = cohort_max_obs[cohort_int]
        retention = []
        for off in full_offsets:
            count = int(row[off])
            if off > max_obs:
                rate = None
            else:
                rate = round(count / size * 100, 2) if size > 0 else 0.0
            retention.append({"month_offset": off, "active": count, "rate": rate})
        matrix_out.append({
            "cohort": _fmt_cohort(cohort_int),
            "size": size,
            "retention": retention,
        })

    # ── Average retention curve (mask-aware) ────────────────────────────────
    rate_matrix = active.div(cohort_sizes, axis=0) * 100
    # NaN-out the unobservable cells so np.nanmean doesn't dilute with zeros.
    obs_mask = pd.DataFrame(
        [[off <= cohort_max_obs[int(c)] for off in full_offsets] for c in rate_matrix.index],
        index=rate_matrix.index, columns=rate_matrix.columns,
    )
    rate_matrix = rate_matrix.where(obs_mask, other=np.nan)

    avg_curve = []
    for off in full_offsets:
        col = rate_matrix[off].dropna()
        if len(col) == 0:
            continue
        avg_curve.append({
            "month_offset": int(off),
            "cohorts_observed": int(len(col)),
            "rate": round(float(col.mean()), 2),
        })

    def _avg_at(off: int) -> float:
        for r in avg_curve:
            if r["month_offset"] == off:
                return r["rate"]
        return 0.0

    # ── Best / worst cohort by 3-month retention ────────────────────────────
    best = worst = None
    if 3 in rate_matrix.columns:
        m3 = rate_matrix[3].dropna()
        # Require minimum cohort size so 1-customer cohorts don't dominate.
        eligible = m3[cohort_sizes.reindex(m3.index) >= 5]
        if not eligible.empty:
            best_idx = int(eligible.idxmax())
            worst_idx = int(eligible.idxmin())
            best = {"cohort": _fmt_cohort(best_idx),
                    "size": int(cohort_sizes.loc[best_idx]),
                    "rate": round(float(eligible.loc[best_idx]), 2)}
            worst = {"cohort": _fmt_cohort(worst_idx),
                     "size": int(cohort_sizes.loc[worst_idx]),
                     "rate": round(float(eligible.loc[worst_idx]), 2)}

    return {
        "summary": {
            "n_cohorts": int(len(cohort_sizes)),
            "n_customers": int(cohort_sizes.sum()),
            "first_cohort": _fmt_cohort(int(cohort_sizes.index.min())),
            "last_cohort": _fmt_cohort(int(cohort_sizes.index.max())),
            "max_month_offset": int(max_offset),
            "avg_retention_m1": _avg_at(1),
            "avg_retention_m3": _avg_at(3),
            "avg_retention_m6": _avg_at(6),
            "avg_retention_m12": _avg_at(12),
        },
        "cohort_matrix": matrix_out,
        "avg_retention_curve": avg_curve,
        "best_cohort_m3": best,
        "worst_cohort_m3": worst,
        "warning": None,
    }
