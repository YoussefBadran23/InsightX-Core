"""A25 — Stock-Out Risk.

For each product, computes recent sales velocity (units/day over the last 30
days) and projects days-to-stockout from `stock_qty`. Flags products by risk
tier: critical (≤7d), warning (8-30d), healthy (>30d), zero-velocity (no
recent sales).

Required columns:  product_id, quantity, stock_qty
Optional:          order_date, reorder_level, product_name, category
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "Which products am I about to run out of?"

RECENT_DAYS = 30
CRITICAL_DAYS = 7
WARNING_DAYS = 30


@register(
    key="A25_stockout_risk",
    analysis_type="product",
    required_cols=["product_id", "quantity", "stock_qty"],
    optional_cols=["order_date", "reorder_level", "product_name", "category"],
    description="Days-to-stockout projection per SKU from recent sales velocity.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["quantity"] = coerce_numeric(df["quantity"]).fillna(0)
    df["stock_qty"] = coerce_numeric(df["stock_qty"]).fillna(0)
    df = df.dropna(subset=["product_id"])
    df["product_id"] = df["product_id"].astype(str)
    df = df[df["quantity"] >= 0]

    if df.empty:
        return _empty("no rows with product_id + quantity + stock_qty")

    has_date = has_col(df, "order_date")
    if has_date:
        df["order_date"] = coerce_date(df["order_date"])

    # Velocity window: prefer recent N days if dates available, else use all data.
    if has_date and df["order_date"].notna().any():
        cutoff = df["order_date"].max() - pd.Timedelta(days=RECENT_DAYS)
        recent = df[df["order_date"] >= cutoff]
        window_days = RECENT_DAYS
    else:
        recent = df
        window_days = 1  # fallback so units/day = total units

    velocity = recent.groupby("product_id")["quantity"].sum() / window_days

    # Stock + reorder level: pick the latest values per product.
    latest = df.drop_duplicates("product_id", keep="last").set_index("product_id")
    stock = latest["stock_qty"]
    reorder = latest.get("reorder_level")
    if reorder is not None:
        reorder = coerce_numeric(reorder).fillna(0)

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

    products: list[dict[str, Any]] = []
    for pid in latest.index:
        v = float(velocity.get(pid, 0))
        s = float(stock.loc[pid])
        if v <= 0:
            days = None
            tier = "no_velocity"
        elif s <= 0:
            days = 0
            tier = "out_of_stock"
        else:
            days = s / v
            if days <= CRITICAL_DAYS:
                tier = "critical"
            elif days <= WARNING_DAYS:
                tier = "warning"
            else:
                tier = "healthy"

        rec: dict[str, Any] = {
            "product_id":      str(pid),
            "name":            name_map.get(str(pid)),
            "category":        cat_map.get(str(pid)),
            "stock_qty":       int(s),
            "velocity_per_day": round(v, 3),
            "days_to_stockout": round(days, 2) if days is not None else None,
            "tier":            tier,
        }
        if reorder is not None:
            rec["reorder_level"] = int(reorder.get(pid, 0))
            rec["below_reorder"] = bool(s <= reorder.get(pid, 0))
        products.append(rec)

    products.sort(key=lambda r: (r["days_to_stockout"] if r["days_to_stockout"] is not None else 9999))

    tier_counts: dict[str, int] = {}
    for p in products:
        tier_counts[p["tier"]] = tier_counts.get(p["tier"], 0) + 1

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    n_critical = tier_counts.get("critical", 0)
    n_warning = tier_counts.get("warning", 0)
    n_out = tier_counts.get("out_of_stock", 0)
    n_no_vel = tier_counts.get("no_velocity", 0)
    needs_attention = n_critical + n_warning + n_out

    headline = build_headline(
        value=needs_attention,
        label="SKUs need restocking attention",
        trend_pct=None,
        period=f"{window_days}-day velocity window",
    )

    bullets: list[str] = []
    # 1 — Headline tier statement
    if n_out >= 1:
        bullets.append(
            f"{n_out} SKU(s) are ALREADY out of stock — every hour you wait, "
            f"you're losing sales to competitors."
        )
    elif n_critical >= 1:
        bullets.append(
            f"{n_critical} SKU(s) will stock out in 7 days or less at current "
            f"velocity — reorder TODAY."
        )
    elif n_warning >= 1:
        bullets.append(
            f"{n_warning} SKU(s) in the warning band (8–30d) — schedule "
            f"reorders this week to stay ahead."
        )
    else:
        bullets.append(
            f"Healthy: all {fmt_int(len(products))} SKUs have >30 days of "
            f"stock at current sales velocity."
        )

    # 2 — Specific product callout
    if products and products[0].get("tier") in ("critical", "out_of_stock"):
        worst = products[0]
        nm = worst.get("name") or worst.get("product_id")
        days_left = worst.get("days_to_stockout")
        if days_left == 0:
            bullets.append(
                f"Highest priority: {str(nm)[:40]} — OUT OF STOCK NOW "
                f"(velocity {worst['velocity_per_day']:.1f} units/day)."
            )
        elif days_left is not None:
            bullets.append(
                f"Highest priority: {str(nm)[:40]} — only "
                f"{int(worst['stock_qty'])} units left, {days_left:.1f} days "
                f"at current pace."
            )
    elif n_no_vel >= 5:
        bullets.append(
            f"{n_no_vel} SKUs had zero sales this window — slow-movers tying "
            f"up inventory cash. Consider clearance or delisting."
        )
    else:
        bullets.append(
            "Set a 14-day reorder alert on your top-20 sellers to never run "
            "out of your best revenue drivers."
        )

    # 3 — Action framing
    if n_critical + n_out >= 3:
        bullets.append(
            "Call your supplier today — express shipping costs less than the "
            "lost sales from a multi-day stockout on hot SKUs."
        )
    elif n_warning >= 5:
        bullets.append(
            "Bulk-order this week instead of weekly tops-ups — better unit "
            "economics and fewer urgent runs to the warehouse."
        )
    else:
        bullets.append(
            "Automate reorder rules: when stock dips below 14-day velocity, "
            "auto-trigger a purchase order to your top supplier."
        )

    actions: list[dict[str, Any]] = [
        action("View restock list", kind="primary",
               deeplink="/dashboard/products?filter=critical&sort=stockout-days",
               icon="arrow"),
    ]
    if n_critical + n_out >= 1:
        actions.append(action(
            "Create purchase orders", kind="warning",
            deeplink="/dashboard/products?action=reorder", icon="arrow",
        ))
    actions.append(action(
        "Export stock report", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
        "summary": {
            "n_products":     len(products),
            "velocity_window_days": window_days,
            "critical_count": tier_counts.get("critical", 0),
            "warning_count":  tier_counts.get("warning", 0),
            "healthy_count":  tier_counts.get("healthy", 0),
            "no_velocity_count": tier_counts.get("no_velocity", 0),
            "out_of_stock_count": tier_counts.get("out_of_stock", 0),
        },
        "by_tier":    [{"tier": t, "count": c} for t, c in tier_counts.items()],
        "critical_products": [p for p in products if p["tier"] in ("critical", "out_of_stock")][:25],
        "all_products": products[:100],  # cap payload
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="SKUs need attention", period="no data"),
            fallback_bullets=[
                "No stock_qty column found — restock alerts need current "
                "inventory levels per SKU.",
                "Include quantity + stock_qty in your upload to unlock "
                "days-to-stockout projections.",
                "Once enabled, this card surfaces your top 25 critical SKUs "
                "with 7-day, 30-day risk tiers.",
            ],
            suggested_actions=[
                action("Add stock column", kind="primary",
                       deeplink="/dashboard/settings/data-sources", icon="arrow"),
            ],
        ),
        "summary": {
            "n_products": 0, "velocity_window_days": RECENT_DAYS,
            "critical_count": 0, "warning_count": 0, "healthy_count": 0,
            "no_velocity_count": 0, "out_of_stock_count": 0,
        },
        "by_tier": [], "critical_products": [], "all_products": [],
        "warning": warning,
    }
