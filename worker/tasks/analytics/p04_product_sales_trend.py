"""P04 — Per-Product Sales Trend.

Weekly time-series for each of the top-N products by revenue. Used for
small-multiples charts on the product detail page.

Required columns:  product_id, total_amount, order_date
Optional:          product_name, net_amount, quantity
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int, fmt_money


QUESTION = "Which products are gaining momentum — and which are fading?"


TOP_N_PRODUCTS = 15
MAX_WEEKS = 52


@register(
    key="P04_product_sales_trend",
    analysis_type="product",
    required_cols=["product_id", "total_amount", "order_date"],
    optional_cols=["product_name", "net_amount", "quantity"],
    description="Weekly revenue + units for top-N products.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["product_id", "order_date", amount_col])
    df = df[df[amount_col] >= 0]
    df["product_id"] = df["product_id"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    has_qty = has_col(df, "quantity")
    if has_qty:
        df["quantity"] = coerce_numeric(df["quantity"]).fillna(0)

    name_map = {}
    if has_col(df, "product_name"):
        name_map = df.dropna(subset=["product_name"]).drop_duplicates("product_id").set_index("product_id")["product_name"].astype(str).to_dict()

    # Pick the top-N products by revenue
    top_products = (
        df.groupby("product_id")[amount_col].sum()
          .sort_values(ascending=False).head(TOP_N_PRODUCTS).index.tolist()
    )

    df["_week"] = df["order_date"].dt.to_period("W").astype(str)

    series = []
    for pid in top_products:
        sub = df[df["product_id"] == pid]
        agg_kwargs = {"revenue": (amount_col, "sum"), "orders": (amount_col, "count")}
        if has_qty:
            agg_kwargs["units"] = ("quantity", "sum")
        weekly = sub.groupby("_week").agg(**agg_kwargs).reset_index().sort_values("_week")
        weekly = weekly.tail(MAX_WEEKS)
        points = []
        for r in weekly.to_dict("records"):
            pt = {
                "week":    r["_week"],
                "revenue": round(float(r["revenue"]), 2),
                "orders":  int(r["orders"]),
            }
            if has_qty:
                pt["units"] = int(r["units"])
            points.append(pt)
        series.append({
            "product_id":    pid,
            "name":          name_map.get(pid),
            "total_revenue": round(float(sub[amount_col].sum()), 2),
            "n_weeks":       int(len(points)),
            "weekly":        points,
        })

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    # Tag each product with a simple momentum score: last-4-weeks revenue
    # vs the 4 weeks before that. We do it here (not in the loop) so the
    # bullets can reference real numbers without doubling the work above.
    momentum: list[dict[str, Any]] = []
    for s in series:
        if len(s["weekly"]) < 8:
            continue
        recent4 = sum(p["revenue"] for p in s["weekly"][-4:])
        prior4 = sum(p["revenue"] for p in s["weekly"][-8:-4])
        if prior4 <= 0:
            continue
        change_pct = (recent4 - prior4) / prior4 * 100
        momentum.append({
            "product_id": s["product_id"],
            "name": s.get("name") or s["product_id"][:16],
            "recent4": recent4,
            "prior4": prior4,
            "change_pct": change_pct,
        })
    rising = sorted(momentum, key=lambda r: r["change_pct"], reverse=True)
    falling = sorted(momentum, key=lambda r: r["change_pct"])

    headline_product = series[0] if series else None
    headline = build_headline(
        value=round(headline_product["total_revenue"], 2) if headline_product else 0,
        label=(f"top product · {headline_product.get('name') or headline_product['product_id'][:18]}"
               if headline_product else "products tracked"),
        period=f"{len(series)} products · last {MAX_WEEKS} weeks",
    )

    bullets: list[str] = []
    if rising and rising[0]["change_pct"] > 10:
        r = rising[0]
        bullets.append(
            f"🔥 {r['name']} is up {r['change_pct']:+.0f}% in the last 4 weeks "
            f"({fmt_money(r['recent4'])} vs {fmt_money(r['prior4'])} prior). Restock & push it."
        )
    elif headline_product:
        bullets.append(
            f"Top performer: {headline_product.get('name') or headline_product['product_id'][:18]} — "
            f"{fmt_money(headline_product['total_revenue'])} lifetime revenue."
        )

    if falling and falling[0]["change_pct"] < -15:
        f = falling[0]
        bullets.append(
            f"⚠️ {f['name']} is down {abs(f['change_pct']):.0f}% in 4 weeks "
            f"({fmt_money(f['recent4'])} vs {fmt_money(f['prior4'])}). Diagnose now."
        )
    elif len(series) >= 5:
        bullets.append(
            f"Tracking weekly trends for the top {len(series)} products — "
            f"any sudden drops will surface here first."
        )

    if len(bullets) < 3:
        bullets.append(
            "Run a weekly review of this card — catching a fading product 2 weeks "
            "earlier than your competitors compounds into market share."
        )

    actions = [
        action("View product trends", kind="primary",
               deeplink="/dashboard/products?focus=P04", icon="arrow"),
    ]
    if falling and falling[0]["change_pct"] < -10:
        actions.append(action(
            "Inspect declining product", kind="warning",
            deeplink=f"/dashboard/products?id={falling[0]['product_id']}", icon="arrow",
        ))
    actions.append(action(
        "Export trends CSV", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
        "summary": {
            "n_products_charted": len(series),
            "total_products":     int(df["product_id"].nunique()),
            "weeks_max":          MAX_WEEKS,
        },
        "series": series,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="products tracked", period="no data"),
            fallback_bullets=[
                "No product trend data yet — needs product_id + order_date + "
                "revenue on each row.",
                "Once available, this card surfaces the weekly velocity of your "
                "top SKUs so you can spot momentum shifts early.",
                "Weekly product trends are the earliest signal of demand change — "
                "catch them 2 weeks before quarterly reports.",
            ],
            suggested_actions=[
                action("Check upload mapping", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {"n_products_charted": 0, "total_products": 0, "weeks_max": MAX_WEEKS},
        "series": [],
        "warning": warning,
    }
