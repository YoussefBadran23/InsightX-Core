"""P05 — Stock Health.

Traffic-light view of every SKU: healthy / low / out-of-stock / overstock.
Distinct from A25 (which forecasts days-to-stockout based on velocity); this
is a snapshot inventory-state report.

Required columns:  product_id, stock_qty
Optional:          reorder_level, product_name, total_amount, category
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "How healthy is my overall inventory right now?"


DEFAULT_LOW_THRESHOLD = 10
OVERSTOCK_FACTOR = 5  # > 5× reorder_level (or 5× median) → overstocked


@register(
    key="P05_stock_health",
    analysis_type="product",
    required_cols=["product_id", "stock_qty"],
    optional_cols=["reorder_level", "product_name", "total_amount", "category"],
    description="Snapshot stock-state classification per SKU.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["stock_qty"] = coerce_numeric(df["stock_qty"]).fillna(0)
    df = df.dropna(subset=["product_id"])
    df["product_id"] = df["product_id"].astype(str)

    if df.empty:
        return _empty("no rows with product_id + stock_qty")

    # Latest stock per product
    latest = df.drop_duplicates("product_id", keep="last").set_index("product_id")

    has_reorder = "reorder_level" in latest.columns
    if has_reorder:
        latest["reorder_level"] = coerce_numeric(latest["reorder_level"]).fillna(DEFAULT_LOW_THRESHOLD)
    else:
        latest["reorder_level"] = DEFAULT_LOW_THRESHOLD

    has_rev = has_col(df, "total_amount")
    if has_rev:
        df["total_amount"] = coerce_numeric(df["total_amount"]).fillna(0)
        rev_per_product = df.groupby("product_id")["total_amount"].sum()
    else:
        rev_per_product = None

    median_stock = float(latest["stock_qty"].median()) or 1.0
    overstock_threshold = max(median_stock * OVERSTOCK_FACTOR,
                              latest["reorder_level"].median() * OVERSTOCK_FACTOR if has_reorder else median_stock * OVERSTOCK_FACTOR)

    def _classify(stock: float, reorder: float) -> str:
        if stock <= 0:
            return "out_of_stock"
        if stock <= reorder:
            return "low"
        if stock > overstock_threshold:
            return "overstock"
        return "healthy"

    latest["status"] = latest.apply(
        lambda r: _classify(float(r["stock_qty"]), float(r["reorder_level"])),
        axis=1,
    )

    name_map = {}
    cat_map = {}
    if has_col(df, "product_name"):
        name_map = df.dropna(subset=["product_name"]).drop_duplicates("product_id").set_index("product_id")["product_name"].astype(str).to_dict()
    if has_col(df, "category"):
        cat_map = df.dropna(subset=["category"]).drop_duplicates("product_id").set_index("product_id")["category"].astype(str).to_dict()

    products = []
    for r in latest.reset_index().to_dict("records"):
        pid = str(r["product_id"])
        rec: dict[str, Any] = {
            "product_id":    pid,
            "name":          name_map.get(pid),
            "category":      cat_map.get(pid),
            "stock_qty":     int(r["stock_qty"]),
            "reorder_level": int(r["reorder_level"]) if has_reorder else None,
            "status":        r["status"],
        }
        if rev_per_product is not None:
            rec["total_revenue"] = round(float(rev_per_product.get(pid, 0)), 2)
        products.append(rec)

    # Status counts
    status_counts: dict[str, int] = {}
    for p in products:
        status_counts[p["status"]] = status_counts.get(p["status"], 0) + 1

    products.sort(key=lambda r: r["stock_qty"])

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    n_out = status_counts.get("out_of_stock", 0)
    n_low = status_counts.get("low", 0)
    n_healthy = status_counts.get("healthy", 0)
    n_over = status_counts.get("overstock", 0)
    total_p = len(products)
    health_pct = round(n_healthy / total_p * 100, 1) if total_p else 0.0

    headline = build_headline(
        value=health_pct,
        label="of SKUs in healthy stock",
        period=f"{fmt_int(total_p)} SKUs total",
    )

    bullets: list[str] = []
    if n_out >= 1:
        bullets.append(
            f"Critical: {n_out} SKU(s) are OUT OF STOCK right now — every hour costs sales."
        )
    elif n_low >= 5:
        bullets.append(
            f"{n_low} SKUs below reorder level — schedule restocks before they hit zero."
        )
    elif health_pct >= 90:
        bullets.append(
            f"Healthy: {health_pct:.1f}% of SKUs are in good stock — inventory is well-managed."
        )
    else:
        bullets.append(
            f"OK: {health_pct:.1f}% healthy stock. {n_low} low + {n_out} out — manageable."
        )

    if n_over >= 5:
        bullets.append(
            f"{n_over} SKUs are overstocked — tying up cash that could be funding growth. "
            f"Run a clearance promo to convert dead inventory to capital."
        )
    elif n_over >= 1:
        bullets.append(
            f"{n_over} SKU(s) are overstocked — small concern; promote them in your next email blast."
        )
    else:
        bullets.append(
            "No overstocked SKUs — inventory turnover is clean. Keep the discipline."
        )

    if n_out + n_low + n_over >= 10:
        bullets.append(
            "Set up automated reorder alerts: 14-day buffer for top sellers, "
            "30-day for mid-tier, manual for long-tail."
        )
    else:
        bullets.append(
            "Inventory is in good shape — invest the freed mental energy in growth, not restocking."
        )

    actions = [
        action("View critical SKUs", kind="primary",
               deeplink="/dashboard/products?filter=low-stock", icon="arrow"),
        action("Export stock report", kind="secondary",
               deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "n_products":          len(products),
            "median_stock":        round(median_stock, 2),
            "overstock_threshold": round(overstock_threshold, 2),
            "out_of_stock_count":  status_counts.get("out_of_stock", 0),
            "low_count":           status_counts.get("low", 0),
            "healthy_count":       status_counts.get("healthy", 0),
            "overstock_count":     status_counts.get("overstock", 0),
        },
        "by_status":   [{"status": s, "count": c} for s, c in status_counts.items()],
        "critical":    [p for p in products if p["status"] in ("out_of_stock", "low")][:50],
        "overstocked": [p for p in products if p["status"] == "overstock"][:25],
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="of SKUs in healthy stock", period="no data"),
            fallback_bullets=[
                "No stock data yet — needs product_id + stock_qty (and ideally reorder_level).",
                "Once tagged, this card shows what % of SKUs are healthy, low, out, or overstocked.",
                "Inventory health is one of the highest-leverage metrics — stockouts kill more SMBs than competition.",
            ],
            suggested_actions=[
                action("Add stock columns", kind="primary",
                       deeplink="/dashboard/settings/data-sources", icon="arrow"),
            ],
        ),
        "summary": {
            "n_products": 0, "median_stock": 0.0, "overstock_threshold": 0.0,
            "out_of_stock_count": 0, "low_count": 0,
            "healthy_count": 0, "overstock_count": 0,
        },
        "by_status": [], "critical": [], "overstocked": [],
        "warning": warning,
    }
