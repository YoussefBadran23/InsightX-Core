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
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "Where is each product in its life — and what's dying out?"


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

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    n_growth = stage_counts.get("growth", 0)
    n_maturity = stage_counts.get("maturity", 0)
    n_intro = stage_counts.get("introduction", 0)
    n_decline = stage_counts.get("decline", 0)
    n_eol = stage_counts.get("end_of_life", 0)

    headline = build_headline(
        value=int(n_growth + n_maturity),
        label="products in healthy stages (growth + maturity)",
        period=f"{fmt_int(n_products)} SKUs tracked",
    )

    bullets: list[str] = []
    # 1 — Healthy vs dying breakdown
    healthy = n_growth + n_maturity
    dying = n_decline + n_eol
    if healthy >= dying * 3:
        bullets.append(
            f"Strong catalog: {fmt_int(healthy)} SKUs in growth/maturity vs "
            f"only {fmt_int(dying)} in decline/end-of-life."
        )
    elif dying >= healthy:
        bullets.append(
            f"More SKUs dying than thriving: {fmt_int(dying)} in decline/EOL vs "
            f"{fmt_int(healthy)} in growth/maturity — refresh the catalog."
        )
    else:
        bullets.append(
            f"Catalog mix: {fmt_int(healthy)} healthy · {fmt_int(dying)} dying · "
            f"{fmt_int(n_intro)} new — a normal product portfolio shape."
        )

    # 2 — End-of-life action prompt
    if n_eol > 0:
        bullets.append(
            f"{fmt_int(n_eol)} products have had no sales in 4+ weeks — candidates "
            f"for delisting, discounting, or a relaunch push."
        )
    elif n_decline > 0:
        bullets.append(
            f"{fmt_int(n_decline)} products are in decline (recent velocity <50% of peak) — "
            f"intervene with marketing or a price test before they fade."
        )
    else:
        bullets.append(
            "No products are flagged as declining — every SKU is either growing, "
            "mature, or freshly launched. Rare and healthy."
        )

    # 3 — Top performer or intro callout
    if products:
        top_growing = next(
            (p for p in products if p["stage"] == "growth"),
            products[0],
        )
        bullets.append(
            f"Top revenue SKU: {top_growing.get('name') or top_growing['product_id'][:16]} "
            f"({top_growing['stage']} stage, {top_growing['current_velocity']:.1f}/week)."
        )
    elif n_intro > 0:
        bullets.append(
            f"{fmt_int(n_intro)} new products under 8 weeks old — measure their growth "
            f"curve weekly to spot winners early."
        )

    actions = [
        action("View by stage", kind="primary",
               deeplink="/dashboard/products?group=lifecycle", icon="arrow"),
    ]
    if n_decline + n_eol > 0:
        actions.append(action(
            "Inspect declining SKUs", kind="warning",
            deeplink="/dashboard/products?stage=decline", icon="arrow",
        ))
    actions.append(action(
        "Export lifecycle report", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
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
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="products tracked", period="no data"),
            fallback_bullets=[
                "No product data yet — lifecycle stages need at least 4 weeks of "
                "order history with product_id + dates.",
                "Once available, this card classifies each SKU as introduction, "
                "growth, maturity, decline, or end-of-life.",
                "Knowing which products are dying lets you prune the catalog "
                "before they bleed shelf space.",
            ],
            suggested_actions=[
                action("Upload more order history", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {
            "n_products": 0, "snapshot_date": None,
            "metric": "n/a", "by_stage": {},
        },
        "by_stage": [], "top_by_revenue": [], "examples_per_stage": {},
        "warning": warning,
    }
