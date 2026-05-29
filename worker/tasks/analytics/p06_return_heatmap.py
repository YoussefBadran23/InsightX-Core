"""P06 — Product Return Heatmap.

A 2-D matrix of return rates: category (rows) × month (columns). Highlights
where return rates are spiking by category over time. Companion to A21
(return_rate) which gives the headline numbers; P06 is the visual heatmap.

Required columns:  product_id, return_flag
Optional:          product_name, category, order_date, total_amount
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "Which category × period combo has the worst returns?"


def _coerce_return_flag(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.astype(bool)
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float).fillna(0) > 0
    truthy = {"true", "1", "yes", "y", "t", "1.0", "returned"}
    return s.astype(str).str.strip().str.lower().isin(truthy)


@register(
    key="P06_return_heatmap",
    analysis_type="product",
    required_cols=["product_id", "return_flag"],
    optional_cols=["product_name", "category", "order_date", "total_amount"],
    description="Category × month return-rate heatmap.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["product_id", "return_flag"])
    df["product_id"] = df["product_id"].astype(str)
    df["_returned"] = _coerce_return_flag(df["return_flag"])

    if df.empty:
        return _empty("no rows with product_id + return_flag")

    has_cat = has_col(df, "category")
    has_date = has_col(df, "order_date")

    # ── Per-product return rate (always available) ──────────────────────────
    name_map = {}
    if has_col(df, "product_name"):
        name_map = df.dropna(subset=["product_name"]).drop_duplicates("product_id").set_index("product_id")["product_name"].astype(str).to_dict()

    prod = df.groupby("product_id").agg(
        orders=("_returned", "size"),
        returns=("_returned", "sum"),
    ).reset_index()
    prod["return_rate_pct"] = (prod["returns"] / prod["orders"] * 100).round(2)
    prod_hot = prod[prod["orders"] >= 5].nlargest(25, "return_rate_pct")

    hot_products = [
        {
            "product_id":      str(r["product_id"]),
            "name":            name_map.get(str(r["product_id"])),
            "orders":          int(r["orders"]),
            "returns":         int(r["returns"]),
            "return_rate_pct": float(r["return_rate_pct"]),
        }
        for r in prod_hot.to_dict("records")
    ]

    # ── Heatmap matrix (only if both category + order_date are present) ────
    heatmap = None
    if has_cat and has_date:
        sub = df.dropna(subset=["category"]).copy()
        sub["category"] = sub["category"].astype(str)
        sub["order_date"] = coerce_date(sub["order_date"])
        sub = sub.dropna(subset=["order_date"])
        if not sub.empty:
            sub["_period"] = sub["order_date"].dt.to_period("M").astype(str)
            cell = sub.groupby(["category", "_period"]).agg(
                orders=("_returned", "size"),
                returns=("_returned", "sum"),
            ).reset_index()
            cell["return_rate_pct"] = (cell["returns"] / cell["orders"] * 100).round(2)
            heatmap = [
                {
                    "category":        str(r["category"]),
                    "period":          str(r["_period"]),
                    "orders":          int(r["orders"]),
                    "returns":         int(r["returns"]),
                    "return_rate_pct": float(r["return_rate_pct"]),
                }
                for r in cell.to_dict("records")
            ]

    overall_rate = round(float(df["_returned"].mean()) * 100, 2)

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    headline = build_headline(
        value=overall_rate,
        label="overall return rate",
        period=f"{fmt_int(len(df))} orders analysed",
    )

    bullets: list[str] = []
    # 1 — Overall rate framing
    if overall_rate >= 10:
        bullets.append(
            f"High return rate: {overall_rate:.1f}% — {fmt_int(int(df['_returned'].sum()))} "
            f"returns. Costing real margin; investigate top categories urgently."
        )
    elif overall_rate >= 5:
        bullets.append(
            f"Moderate return rate: {overall_rate:.1f}% — typical for fashion / "
            f"sizing-sensitive products. Aim for <5%."
        )
    else:
        bullets.append(
            f"Healthy: {overall_rate:.1f}% return rate. "
            f"{fmt_int(int(df['_returned'].sum()))} returns is well within industry norms."
        )

    # 2 — Worst product/category callout
    if hot_products:
        worst = hot_products[0]
        nm = worst.get("name") or worst.get("product_id")
        bullets.append(
            f"Worst SKU: {str(nm)[:40]} — {worst['return_rate_pct']:.1f}% return rate "
            f"({worst['returns']}/{worst['orders']} orders returned)."
        )
    elif heatmap:
        worst_cell = max(heatmap, key=lambda c: c.get("return_rate_pct", 0))
        bullets.append(
            f"Worst category × month: {worst_cell['category']} in {worst_cell['period']} — "
            f"{worst_cell['return_rate_pct']:.1f}% return rate."
        )
    else:
        bullets.append(
            "Need category + order_date columns to surface the worst category × "
            "month combos."
        )

    # 3 — Action
    if overall_rate >= 8:
        bullets.append(
            "Audit your top-5 returned products' photos, sizing guides, and descriptions — "
            "expectation mismatch drives most returns."
        )
    elif hot_products and len(hot_products) >= 3:
        bullets.append(
            "Bundle the top-3 returned products with a sizing guide or trial-period "
            "policy to reduce returns by 20-30%."
        )
    else:
        bullets.append(
            "Track returns by reason code (size, quality, damaged) — root-cause data "
            "unlocks the next round of improvements."
        )

    actions = [
        action("View return heatmap", kind="primary",
               deeplink="/dashboard/analytics?focus=P06", icon="arrow"),
        action("Export returns CSV", kind="secondary", deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "n_orders":               int(len(df)),
            "n_returns":              int(df["_returned"].sum()),
            "overall_return_rate_pct": overall_rate,
            "n_categories":           int(df["category"].nunique()) if has_cat else 0,
            "has_heatmap":            heatmap is not None,
        },
        "hot_products": hot_products,
        "heatmap":      heatmap,
        "warning": None if heatmap is not None else
                   "no heatmap — needs category + order_date columns",
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="overall return rate", period="no data"),
            fallback_bullets=[
                "No return data yet — add a return_flag column (true/false per order line).",
                "Once tagged, this card surfaces worst categories × months and the top-25 highest-return products.",
                "Tracking returns by category is the first step to fixing them.",
            ],
            suggested_actions=[
                action("Add return_flag column", kind="primary",
                       deeplink="/dashboard/settings/data-sources", icon="arrow"),
            ],
        ),
        "summary": {
            "n_orders": 0, "n_returns": 0, "overall_return_rate_pct": 0.0,
            "n_categories": 0, "has_heatmap": False,
        },
        "hot_products": [], "heatmap": None,
        "warning": warning,
    }
