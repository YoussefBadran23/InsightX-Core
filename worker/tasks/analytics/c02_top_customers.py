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

    return {
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
        "summary": {
            "n_customers": 0, "total_revenue": 0.0,
            "top_10_pct_share": 0.0, "top_50_pct_share": 0.0,
            "top_100_pct_share": 0.0,
        },
        "top_customers": [],
        "warning": warning,
    }
