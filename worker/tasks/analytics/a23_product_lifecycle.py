"""A23 — Product Life-Cycle / Sales Velocity Decay.

For each product, computes weekly sales velocity (units sold per week if
quantity is available, else orders per week). Classifies products into
lifecycle stages by comparing recent velocity to peak velocity:

- introduction:   <8 weeks since first sale
- growth:         current velocity is 80%+ of peak, peak is recent
- maturity:       current velocity is 50-100% of peak, plateau
- decline:        current velocity < 50% of peak AND peak was >8 weeks ago
- end-of-life:    no sales in last 4 weeks AND product has history

Required columns:  product_id, total_amount, order_date
Optional:          quantity, product_name, category, product_status
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


MIN_WEEKS_FOR_LIFECYCLE = 4
INTRO_WEEKS = 8
EOL_QUIET_WEEKS = 4
TOP_N = 20


def _classify(weeks_alive: int, weeks_since_peak: int,
              current_vel: float, peak_vel: float,
              weeks_since_last_sale: int) -> str:
    if weeks_since_last_sale >= EOL_QUIET_WEEKS and weeks_alive > INTRO_WEEKS:
        return "end_of_life"
    if weeks_alive <= INTRO_WEEKS:
        return "introduction"
    if peak_vel == 0:
        return "decline"
    ratio = current_vel / peak_vel
    if ratio >= 0.8:
        return "growth" if weeks_since_peak <= 4 else "maturity"
    if ratio >= 0.5:
        return "maturity"
    return "decline"


@register(
    key="A23_product_lifecycle",
    analysis_type="product",
    required_cols=["product_id", "total_amount", "order_date"],
    optional_cols=["quantity", "product_name", "category", "product_status"],
    description="Product life-cycle stages from weekly sales-velocity decay.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    df = df.dropna(subset=["product_id", "order_date", "total_amount"])
    df["product_id"] = df["product_id"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    has_qty = has_col(df, "quantity")
    if has_qty:
        df["quantity"] = coerce_numeric(df["quantity"]).fillna(1)
    metric_col = "quantity" if has_qty else "total_amount"

    snapshot = df["order_date"].max()
    df["_week"] = df["order_date"].dt.to_period("W")
    snap_week = pd.Period(snapshot, freq="W")

    # ── Per (product, week) aggregate ───────────────────────────────────────
    pw = df.groupby(["product_id", "_week"]).agg(
        units=("quantity", "sum") if has_qty else ("product_id", "count"),
        revenue=("total_amount", "sum"),
    ).reset_index()

    # ── Name + category maps ────────────────────────────────────────────────
    name_map = {}
    cat_map = {}
    if has_col(df, "product_name"):
        name_map = (
            df.dropna(subset=["product_name"])
              .drop_duplicates("product_id")
              .set_index("product_id")["product_name"].astype(str).to_dict()
        )
    if has_col(df, "category"):
        cat_map = (
            df.dropna(subset=["category"])
              .drop_duplicates("product_id")
              .set_index("product_id")["category"].astype(str).to_dict()
        )

    # ── Per-product lifecycle metrics ───────────────────────────────────────
    products: list[dict[str, Any]] = []
    for pid, grp in pw.groupby("product_id"):
        grp = grp.sort_values("_week")
        weeks_alive = (snap_week - grp["_week"].iloc[0]).n + 1
        weeks_since_last_sale = (snap_week - grp["_week"].iloc[-1]).n
        if weeks_alive < MIN_WEEKS_FOR_LIFECYCLE:
            stage = "introduction"
            peak_vel = float(grp["units"].max())
            current_vel = float(grp["units"].iloc[-1])
        else:
            # 4-week trailing average for current velocity vs peak.
            recent = grp.tail(4)
            current_vel = float(recent["units"].mean())
            peak_vel = float(grp["units"].max())
            peak_week_idx = grp["units"].idxmax()
            peak_week = grp.loc[peak_week_idx, "_week"]
            weeks_since_peak = (snap_week - peak_week).n
            stage = _classify(weeks_alive, weeks_since_peak, current_vel, peak_vel, weeks_since_last_sale)

        products.append({
            "product_id":            str(pid),
            "name":                  name_map.get(str(pid)),
            "category":              cat_map.get(str(pid)),
            "stage":                 stage,
            "weeks_alive":           int(weeks_alive),
            "weeks_since_last_sale": int(weeks_since_last_sale),
            "current_velocity":      round(current_vel, 2),
            "peak_velocity":         round(peak_vel, 2),
            "total_units":           int(grp["units"].sum()),
            "total_revenue":         round(float(grp["revenue"].sum()), 2),
        })

    n_products = len(products)
    stage_counts: dict[str, int] = {}
    for p in products:
        stage_counts[p["stage"]] = stage_counts.get(p["stage"], 0) + 1

    by_stage = [
        {
            "stage":  s,
            "count":  c,
            "pct":    round(c / n_products * 100, 2) if n_products else 0.0,
        }
        for s, c in sorted(stage_counts.items(), key=lambda x: -x[1])
    ]

    # ── Examples per stage ──────────────────────────────────────────────────
    products.sort(key=lambda r: r["total_revenue"], reverse=True)
    examples_per_stage: dict[str, list[dict[str, Any]]] = {}
    for p in products:
        examples_per_stage.setdefault(p["stage"], [])
        if len(examples_per_stage[p["stage"]]) < 5:
            examples_per_stage[p["stage"]].append(p)

    return {
        "summary": {
            "n_products":   n_products,
            "snapshot_date": snapshot.date().isoformat(),
            "metric":       "units sold per week" if has_qty else "orders per week",
            "by_stage":     {s: c for s, c in stage_counts.items()},
        },
        "by_stage":          by_stage,
        "top_by_revenue":    products[:TOP_N],
        "examples_per_stage": examples_per_stage,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_products": 0, "snapshot_date": None,
            "metric": "n/a", "by_stage": {},
        },
        "by_stage": [], "top_by_revenue": [], "examples_per_stage": {},
        "warning": warning,
    }
