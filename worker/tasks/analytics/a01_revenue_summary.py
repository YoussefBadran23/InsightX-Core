"""A01 — Revenue Summary.

Computes total revenue, daily/weekly/monthly aggregations, and breakdowns
by region and currency. The primary revenue figure prefers `net_amount` if
available (already discount-adjusted), otherwise falls back to `total_amount`.

Required columns:  total_amount, order_date
Optional columns:  net_amount, region, currency, discount_amount

Output schema::

    {
      "summary": {
        "total":       float,
        "avg_daily":   float,
        "avg_weekly":  float,
        "avg_monthly": float,
        "order_count": int,
        "date_range":  {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "n_days": int}
      },
      "by_period": {
        "daily":   [{"date": "YYYY-MM-DD", "revenue": float, "orders": int}],
        "weekly":  [{"period": "YYYY-Wnn",  "revenue": float, "orders": int}],
        "monthly": [{"period": "YYYY-MM",   "revenue": float, "orders": int}]
      },
      "by_region":   [{"region": str,   "revenue": float, "pct": float}],
      "by_currency": [{"currency": str, "revenue": float, "pct": float}],
      "top_days":    [{"date": "YYYY-MM-DD", "revenue": float}],   # 10 largest
      "discount_summary": {                                          # if discount_amount present
        "total_discount":   float,
        "discount_pct":     float,
        "orders_with_disc": int
      }
    }
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


@register(
    key="A01_revenue_summary",
    analysis_type="revenue",
    required_cols=["total_amount", "order_date"],
    optional_cols=["net_amount", "region", "currency", "discount_amount"],
    description="Total revenue breakdown by region, period, and category.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()

    # Coerce types defensively. The seed CSVs may carry currency symbols on
    # `total_amount` (variant 03_bad_types) and mixed date formats.
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["order_date", amount_col])

    # Drop sub-zero noise so anomaly modules can flag negatives separately
    # instead of having the headline revenue silently shrink. We keep zeros.
    df = df[df[amount_col] >= 0]

    if df.empty:
        return {
            "summary": {
                "total": 0.0, "avg_daily": 0.0, "avg_weekly": 0.0,
                "avg_monthly": 0.0, "order_count": 0,
                "date_range": {"start": None, "end": None, "n_days": 0},
            },
            "by_period": {"daily": [], "weekly": [], "monthly": []},
            "by_region": [], "by_currency": [], "top_days": [],
        }

    total = float(df[amount_col].sum())
    date_min, date_max = df["order_date"].min(), df["order_date"].max()
    n_days = max((date_max - date_min).days + 1, 1)

    # ── Aggregations ────────────────────────────────────────────────────────
    daily = (
        df.groupby(df["order_date"].dt.date)
          .agg(revenue=(amount_col, "sum"), orders=(amount_col, "count"))
          .reset_index().rename(columns={"order_date": "date"})
          .sort_values("date")
    )
    weekly = (
        df.groupby(df["order_date"].dt.to_period("W"))
          .agg(revenue=(amount_col, "sum"), orders=(amount_col, "count"))
          .reset_index().rename(columns={"order_date": "period"})
    )
    weekly["period"] = weekly["period"].astype(str)
    monthly = (
        df.groupby(df["order_date"].dt.to_period("M"))
          .agg(revenue=(amount_col, "sum"), orders=(amount_col, "count"))
          .reset_index().rename(columns={"order_date": "period"})
    )
    monthly["period"] = monthly["period"].astype(str)

    # ── Categorical breakdowns ──────────────────────────────────────────────
    breakdowns: dict[str, list] = {}
    for col in ("region", "currency"):
        if has_col(df, col):
            agg = (
                df.groupby(col)[amount_col].sum()
                  .reset_index().rename(columns={amount_col: "revenue"})
            )
            agg["pct"] = (agg["revenue"] / total * 100).round(2)
            breakdowns[col] = agg.sort_values("revenue", ascending=False).to_dict("records")

    # ── Optional discount summary ───────────────────────────────────────────
    discount_summary = None
    if has_col(df, "discount_amount"):
        df["discount_amount"] = coerce_numeric(df["discount_amount"]).fillna(0)
        total_disc = float(df["discount_amount"].sum())
        gross = float(df["total_amount"].sum())
        discount_summary = {
            "total_discount": round(total_disc, 2),
            "discount_pct": round(100 * total_disc / gross, 2) if gross > 0 else 0.0,
            "orders_with_disc": int((df["discount_amount"] > 0).sum()),
        }

    return {
        "summary": {
            "total": round(total, 2),
            "avg_daily": round(total / n_days, 2),
            "avg_weekly": round(total / max(len(weekly), 1), 2),
            "avg_monthly": round(total / max(len(monthly), 1), 2),
            "order_count": int(len(df)),
            "date_range": {
                "start": date_min.date().isoformat(),
                "end": date_max.date().isoformat(),
                "n_days": int(n_days),
            },
        },
        "by_period": {
            "daily":   [{"date": str(r["date"]), "revenue": round(r["revenue"], 2), "orders": int(r["orders"])}
                        for r in daily.to_dict("records")],
            "weekly":  [{"period": r["period"], "revenue": round(r["revenue"], 2), "orders": int(r["orders"])}
                        for r in weekly.to_dict("records")],
            "monthly": [{"period": r["period"], "revenue": round(r["revenue"], 2), "orders": int(r["orders"])}
                        for r in monthly.to_dict("records")],
        },
        "by_region":   breakdowns.get("region", []),
        "by_currency": breakdowns.get("currency", []),
        "top_days":    [{"date": str(r["date"]), "revenue": round(r["revenue"], 2)}
                        for r in daily.nlargest(10, "revenue").to_dict("records")],
        "discount_summary": discount_summary,
    }
