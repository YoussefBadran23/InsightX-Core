"""A04 — Gross Margin Analysis.

Compares per-order cost vs revenue to expose where the business actually makes
money. Surfaces loss-makers (margin <0%), thin-margin segments, and the
products/categories carrying the bottom line.

Margin formulas
---------------
- **margin($)** = revenue - cost
- **margin(%)** = (revenue - cost) / revenue × 100  (when revenue > 0)

If `net_amount` is available we use it for the revenue side (already
discount-adjusted). Otherwise `total_amount`.

Required columns:  cost_amount, total_amount
Optional columns:  net_amount, order_date, product_id, product_name,
                   category, brand, region, quantity

Output schema::

    {
      "summary": {
        "total_revenue":     float,
        "total_cost":        float,
        "gross_margin":      float,     # absolute
        "gross_margin_pct":  float,     # %
        "n_orders":          int,
        "n_loss_making":     int,
        "loss_making_pct":   float,
        "avg_order_margin":  float,
        "avg_order_margin_pct": float
      },
      "margin_distribution": {
        "negative": int, "0-10%": int, "10-25%": int, "25-50%": int,
        "50-75%": int, "75-100%": int, "above_100%": int
      },
      "by_category":   [...],   # if category column present
      "by_brand":      [...],   # if brand column present
      "by_region":     [...],   # if region column present
      "by_period":     {"monthly": [...]},  # if order_date present
      "top_margin_products":   [...],  # top 20 by absolute margin contribution
      "loss_makers":           [...],  # bottom 20 (most negative margin)
      "warning": str | None
    }
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


def _bucket_margins(pct_series: pd.Series) -> dict[str, int]:
    """Bin order-level margin% into business-meaningful buckets."""
    bins = [-float("inf"), 0, 10, 25, 50, 75, 100, float("inf")]
    labels = ["negative", "0-10%", "10-25%", "25-50%", "50-75%", "75-100%", "above_100%"]
    binned = pd.cut(pct_series, bins=bins, labels=labels, include_lowest=True, right=False)
    counts = binned.value_counts().reindex(labels, fill_value=0)
    return {k: int(v) for k, v in counts.items()}


def _group_margin(df: pd.DataFrame, by: str, total_revenue: float) -> list[dict[str, Any]]:
    agg = (
        df.groupby(by)
          .agg(revenue=("_revenue", "sum"),
               cost=("_cost", "sum"),
               orders=("_revenue", "count"))
          .reset_index()
    )
    agg["margin"] = agg["revenue"] - agg["cost"]
    agg["margin_pct"] = (agg["margin"] / agg["revenue"].replace(0, pd.NA) * 100).round(2)
    agg["rev_share_pct"] = (agg["revenue"] / total_revenue * 100).round(2) if total_revenue > 0 else 0.0
    agg = agg.sort_values("margin", ascending=False)
    return [
        {
            by: str(r[by]),
            "revenue": round(float(r["revenue"]), 2),
            "cost": round(float(r["cost"]), 2),
            "margin": round(float(r["margin"]), 2),
            "margin_pct": float(r["margin_pct"]) if pd.notna(r["margin_pct"]) else 0.0,
            "orders": int(r["orders"]),
            "rev_share_pct": float(r["rev_share_pct"]),
        }
        for r in agg.to_dict("records")
    ]


@register(
    key="A04_gross_margin",
    analysis_type="revenue",
    required_cols=["cost_amount", "total_amount"],
    optional_cols=["net_amount", "order_date", "product_id", "product_name",
                   "category", "brand", "region", "quantity"],
    description="Gross margin analysis ($ and %) with category/brand/region breakdowns.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    df["cost_amount"] = coerce_numeric(df["cost_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    if has_col(df, "order_date"):
        df["order_date"] = coerce_date(df["order_date"])

    revenue_col = "net_amount" if has_col(df, "net_amount") else "total_amount"

    # We KEEP loss-making rows (cost > revenue) — they're the signal we want
    # to surface. We only drop rows with NaN / non-positive revenue (can't
    # compute margin pct against zero or missing).
    df = df.dropna(subset=[revenue_col, "cost_amount"])
    df = df[df[revenue_col] > 0]
    df = df[df["cost_amount"] >= 0]

    if df.empty:
        return {
            "summary": {
                "total_revenue": 0.0, "total_cost": 0.0,
                "gross_margin": 0.0, "gross_margin_pct": 0.0,
                "n_orders": 0, "n_loss_making": 0, "loss_making_pct": 0.0,
                "avg_order_margin": 0.0, "avg_order_margin_pct": 0.0,
            },
            "margin_distribution": {},
            "by_category": [], "by_brand": [], "by_region": [],
            "by_period": {"monthly": []},
            "top_margin_products": [], "loss_makers": [],
            "warning": "no rows with both cost and revenue after coercion",
        }

    # Normalize to internal columns so groupby helpers don't care which
    # revenue source was used.
    df["_revenue"] = df[revenue_col]
    df["_cost"] = df["cost_amount"]
    df["_margin"] = df["_revenue"] - df["_cost"]
    df["_margin_pct"] = (df["_margin"] / df["_revenue"] * 100)

    total_revenue = float(df["_revenue"].sum())
    total_cost = float(df["_cost"].sum())
    gross_margin = total_revenue - total_cost
    gm_pct = (gross_margin / total_revenue * 100) if total_revenue > 0 else 0.0
    n_loss = int((df["_margin"] < 0).sum())

    # ── Categorical breakdowns ──────────────────────────────────────────────
    breakdowns: dict[str, list] = {}
    for col in ("category", "brand", "region"):
        if has_col(df, col):
            sub = df.dropna(subset=[col])
            sub = sub.assign(**{col: sub[col].astype(str)})
            breakdowns[col] = _group_margin(sub, col, total_revenue)

    # ── Monthly trend ───────────────────────────────────────────────────────
    by_period: dict[str, list] = {"monthly": []}
    if has_col(df, "order_date"):
        sub = df.dropna(subset=["order_date"]).copy()
        if not sub.empty:
            sub["_period"] = sub["order_date"].dt.to_period("M").astype(str)
            by_period["monthly"] = _group_margin(sub, "_period", total_revenue)
            for r in by_period["monthly"]:
                r["period"] = r.pop("_period")
            by_period["monthly"].sort(key=lambda r: r["period"])

    # ── Per-product views ───────────────────────────────────────────────────
    top_margin_products: list[dict[str, Any]] = []
    loss_makers: list[dict[str, Any]] = []
    if has_col(df, "product_id"):
        name_map: dict[str, str] = {}
        if has_col(df, "product_name"):
            name_map = (
                df.dropna(subset=["product_name"])
                  .drop_duplicates(subset="product_id")
                  .set_index("product_id")["product_name"].astype(str).to_dict()
            )

        prod = (
            df.groupby(df["product_id"].astype(str))
              .agg(revenue=("_revenue", "sum"),
                   cost=("_cost", "sum"),
                   orders=("_revenue", "count"))
              .reset_index().rename(columns={"product_id": "product_id"})
        )
        prod["margin"] = prod["revenue"] - prod["cost"]
        prod["margin_pct"] = (prod["margin"] / prod["revenue"].replace(0, pd.NA) * 100).round(2)

        top = prod.nlargest(20, "margin")
        bottom = prod[prod["margin"] < 0].nsmallest(20, "margin")

        for r in top.to_dict("records"):
            top_margin_products.append({
                "product_id": str(r["product_id"]),
                "name": name_map.get(str(r["product_id"])),
                "revenue": round(float(r["revenue"]), 2),
                "cost": round(float(r["cost"]), 2),
                "margin": round(float(r["margin"]), 2),
                "margin_pct": float(r["margin_pct"]) if pd.notna(r["margin_pct"]) else 0.0,
                "orders": int(r["orders"]),
            })
        for r in bottom.to_dict("records"):
            loss_makers.append({
                "product_id": str(r["product_id"]),
                "name": name_map.get(str(r["product_id"])),
                "revenue": round(float(r["revenue"]), 2),
                "cost": round(float(r["cost"]), 2),
                "margin": round(float(r["margin"]), 2),
                "margin_pct": float(r["margin_pct"]) if pd.notna(r["margin_pct"]) else 0.0,
                "orders": int(r["orders"]),
            })

    return {
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "gross_margin": round(gross_margin, 2),
            "gross_margin_pct": round(gm_pct, 2),
            "n_orders": int(len(df)),
            "n_loss_making": n_loss,
            "loss_making_pct": round(n_loss / len(df) * 100, 2),
            "avg_order_margin": round(float(df["_margin"].mean()), 2),
            "avg_order_margin_pct": round(float(df["_margin_pct"].mean()), 2),
        },
        "margin_distribution": _bucket_margins(df["_margin_pct"]),
        "by_category": breakdowns.get("category", []),
        "by_brand":    breakdowns.get("brand", []),
        "by_region":   breakdowns.get("region", []),
        "by_period":   by_period,
        "top_margin_products": top_margin_products,
        "loss_makers": loss_makers,
        "warning": None,
    }
