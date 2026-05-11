"""P03 — Brand Performance.

Revenue + market share by brand. Surfaces the dominant brands and a Herfindahl
concentration index (0..1) so the dashboard can flag "brand-monopoly" datasets
vs evenly-spread ones.

Required columns:  brand, total_amount
Optional:          product_id, net_amount, order_date
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


@register(
    key="P03_brand_performance",
    analysis_type="product",
    required_cols=["brand", "total_amount"],
    optional_cols=["product_id", "net_amount", "order_date"],
    description="Revenue + market share + concentration index by brand.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["brand", amount_col])
    df = df[df[amount_col] >= 0]
    df["brand"] = df["brand"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    agg_kwargs = {"revenue": (amount_col, "sum"), "orders": (amount_col, "count")}
    if has_col(df, "product_id"):
        df["product_id"] = df["product_id"].astype(str)
        agg_kwargs["unique_products"] = ("product_id", "nunique")

    brand = df.groupby("brand").agg(**agg_kwargs).reset_index()
    total_rev = float(brand["revenue"].sum())
    brand = brand.sort_values("revenue", ascending=False).reset_index(drop=True)
    brand["rank"]    = brand.index + 1
    brand["rev_pct"] = (brand["revenue"] / total_rev * 100).round(2) if total_rev else 0.0

    by_brand = []
    for r in brand.to_dict("records"):
        rec: dict[str, Any] = {
            "brand":   str(r["brand"]),
            "rank":    int(r["rank"]),
            "revenue": round(float(r["revenue"]), 2),
            "orders":  int(r["orders"]),
            "rev_pct": float(r["rev_pct"]),
        }
        if "unique_products" in r:
            rec["unique_products"] = int(r["unique_products"])
        by_brand.append(rec)

    # Herfindahl (concentration): sum of squared fractional shares.
    fractions = brand["rev_pct"] / 100.0
    hhi = float((fractions ** 2).sum())
    if hhi < 0.15:
        hhi_label = "diffuse"
    elif hhi < 0.25:
        hhi_label = "moderate"
    else:
        hhi_label = "concentrated"

    # Monthly trend for top-5 brands
    monthly_trend = None
    if has_col(df, "order_date"):
        sub = df.copy()
        sub["order_date"] = coerce_date(sub["order_date"])
        sub = sub.dropna(subset=["order_date"])
        top_5_brands = [b["brand"] for b in by_brand[:5]]
        sub = sub[sub["brand"].isin(top_5_brands)]
        if not sub.empty:
            sub["_period"] = sub["order_date"].dt.to_period("M").astype(str)
            trend = sub.groupby(["_period", "brand"])[amount_col].sum().reset_index()
            monthly_trend = [
                {"period": r["_period"], "brand": str(r["brand"]), "revenue": round(float(r[amount_col]), 2)}
                for r in trend.to_dict("records")
            ]

    return {
        "summary": {
            "n_brands":      int(len(by_brand)),
            "total_revenue": round(total_rev, 2),
            "top_brand":     by_brand[0] if by_brand else None,
            "top_3_share":   round(sum(b["rev_pct"] for b in by_brand[:3]), 2),
            "herfindahl_index":  round(hhi, 4),
            "herfindahl_label":  hhi_label,
        },
        "by_brand":      by_brand,
        "monthly_trend": monthly_trend,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_brands": 0, "total_revenue": 0.0, "top_brand": None,
            "top_3_share": 0.0, "herfindahl_index": 0.0, "herfindahl_label": "diffuse",
        },
        "by_brand": [], "monthly_trend": None,
        "warning": warning,
    }
