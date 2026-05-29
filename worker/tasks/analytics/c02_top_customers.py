"""C02 — Top Customers by Revenue.

Leaderboard of biggest spenders with their order count and AOV. Lighter
than A10 (lifetime stats with distributions) — this is the at-a-glance
"who are the top 50 customers" view used on the home dashboard.

Required columns:  customer_id, total_amount
Optional:          customer_name, customer_email, order_date, net_amount, region
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_money


QUESTION = "Who are my top 10 customers by total spend?"


TOP_N = 50


@register(
    key="C02_top_customers",
    analysis_type="customer",
    required_cols=["customer_id", "total_amount"],
    optional_cols=["customer_name", "customer_email", "order_date", "net_amount", "region"],
    description="Top-N customers by total revenue.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", amount_col])
    df = df[df[amount_col] >= 0]
    df["customer_id"] = df["customer_id"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    if has_col(df, "order_date"):
        df["order_date"] = coerce_date(df["order_date"])

    agg_kwargs = {
        "lifetime_value": (amount_col, "sum"),
        "n_orders":       (amount_col, "count"),
    }
    if has_col(df, "order_date"):
        agg_kwargs["first_order"] = ("order_date", "min")
        agg_kwargs["last_order"]  = ("order_date", "max")

    cust = df.groupby("customer_id").agg(**agg_kwargs).reset_index()
    cust["aov"] = (cust["lifetime_value"] / cust["n_orders"]).round(2)

    # Display columns
    name_map = {}
    email_map = {}
    region_map = {}
    if has_col(df, "customer_name"):
        name_map = df.dropna(subset=["customer_name"]).drop_duplicates("customer_id").set_index("customer_id")["customer_name"].astype(str).to_dict()
    if has_col(df, "customer_email"):
        email_map = df.dropna(subset=["customer_email"]).drop_duplicates("customer_id").set_index("customer_id")["customer_email"].astype(str).to_dict()
    if has_col(df, "region"):
        region_map = df.dropna(subset=["region"]).drop_duplicates("customer_id").set_index("customer_id")["region"].astype(str).to_dict()

    total_rev = float(cust["lifetime_value"].sum())
    cust = cust.sort_values("lifetime_value", ascending=False).reset_index(drop=True)
    cust["rank"]    = cust.index + 1
    cust["rev_pct"] = (cust["lifetime_value"] / total_rev * 100).round(3) if total_rev > 0 else 0.0

    top = cust.head(TOP_N)
    top_records = []
    for r in top.to_dict("records"):
        rec: dict[str, Any] = {
            "rank":           int(r["rank"]),
            "customer_id":    str(r["customer_id"]),
            "name":           name_map.get(str(r["customer_id"])),
            "email":          email_map.get(str(r["customer_id"])),
            "region":         region_map.get(str(r["customer_id"])),
            "lifetime_value": round(float(r["lifetime_value"]), 2),
            "n_orders":       int(r["n_orders"]),
            "aov":            float(r["aov"]),
            "rev_pct":        float(r["rev_pct"]),
        }
        if "first_order" in r and pd.notna(r.get("first_order")):
            rec["first_order"] = str(pd.to_datetime(r["first_order"]).date())
            rec["last_order"]  = str(pd.to_datetime(r["last_order"]).date())
        top_records.append(rec)

    # Concentration: what % of revenue from top N customers
    top_10_rev = float(cust.head(10)["lifetime_value"].sum())
    top_50_rev = float(cust.head(50)["lifetime_value"].sum())
    top_100_rev = float(cust.head(100)["lifetime_value"].sum())

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    top_10_share = round(top_10_rev / total_rev * 100, 1) if total_rev else 0.0
    top1 = top_records[0] if top_records else None

    headline = build_headline(
        value=round(top_10_rev, 2),
        label="revenue from top 10 customers",
        period=f"{int(len(cust)):,} total customers",
    )

    bullets: list[str] = []
    if top1:
        nm = top1.get("name") or top1.get("email") or top1.get("customer_id")
        bullets.append(
            f"#1 customer: {str(nm)[:40]} — {fmt_money(top1['lifetime_value'])} "
            f"across {top1['n_orders']} orders ({top1['rev_pct']:.1f}% of all revenue)."
        )
    else:
        bullets.append(f"Tracking {int(len(cust)):,} customers in total.")

    if top_10_share >= 50:
        bullets.append(
            f"Top 10 customers carry {top_10_share:.0f}% of revenue — "
            f"high concentration risk. Lose one and revenue takes a real hit."
        )
    elif top_10_share >= 25:
        bullets.append(
            f"Top 10 customers contribute {top_10_share:.0f}% of revenue — "
            f"meaningful but balanced concentration."
        )
    else:
        bullets.append(
            f"Revenue is spread broadly — top 10 only contribute {top_10_share:.0f}%. "
            f"Lots of customers, no single point of failure."
        )

    if top_10_share >= 30:
        bullets.append(
            "Personally call your top 5 customers this quarter — even a "
            "10-minute conversation locks in long-term loyalty."
        )
    else:
        bullets.append(
            "Build a VIP tier for your top 5% — exclusive access, early product "
            "drops, personal account manager. Turn 'customers' into 'fans'."
        )

    actions = [
        action("View VIP list", kind="primary",
               deeplink="/dashboard/customers?filter=vip", icon="arrow"),
        action("Export top customers", kind="secondary", deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "n_customers":       int(len(cust)),
            "total_revenue":     round(total_rev, 2),
            "top_10_pct_share":  round(top_10_rev  / total_rev * 100, 2) if total_rev else 0.0,
            "top_50_pct_share":  round(top_50_rev  / total_rev * 100, 2) if total_rev else 0.0,
            "top_100_pct_share": round(top_100_rev / total_rev * 100, 2) if total_rev else 0.0,
        },
        "top_customers": top_records,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="revenue from top customers", period="no data"),
            fallback_bullets=[
                "No customer data yet — top customers needs customer_id linked to revenue.",
                "Once data exists, this card surfaces the names of your highest-LTV customers.",
                "Treat those customers like VIPs — they fund the rest of the business.",
            ],
            suggested_actions=[
                action("Upload data", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {
            "n_customers": 0, "total_revenue": 0.0,
            "top_10_pct_share": 0.0, "top_50_pct_share": 0.0,
            "top_100_pct_share": 0.0,
        },
        "top_customers": [],
        "warning": warning,
    }
