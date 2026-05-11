"""C03 — Customer Geographic Distribution.

Map-friendly per-region / per-city customer counts. Eligible if at least one
of (customer_city, region) is present; country adds an extra level.

Required columns:  customer_id   (city OR region required, OR-condition)
Optional:          customer_city, region, country, country_code, total_amount
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_numeric, has_col, register


@register(
    key="C03_geo_distribution",
    analysis_type="customer",
    required_cols=["customer_id"],
    optional_cols=["customer_city", "region", "country", "country_code", "total_amount"],
    description="Customer count + revenue by city/region/country.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["customer_id"])
    df["customer_id"] = df["customer_id"].astype(str)
    has_amt = has_col(df, "total_amount")
    if has_amt:
        df["total_amount"] = coerce_numeric(df["total_amount"]).fillna(0)

    avail = {c: has_col(df, c) for c in ("customer_city", "region", "country", "country_code")}
    if not (avail["customer_city"] or avail["region"] or avail["country"]):
        return _empty("dataset has none of customer_city / region / country")

    n_customers = int(df["customer_id"].nunique())

    def _by(col: str) -> list[dict[str, Any]] | None:
        if not avail[col]:
            return None
        sub = df.dropna(subset=[col]).copy()
        sub[col] = sub[col].astype(str)
        agg_kwargs = {
            "customers": ("customer_id", "nunique"),
            "orders":    ("customer_id", "size"),
        }
        if has_amt:
            agg_kwargs["revenue"] = ("total_amount", "sum")
        g = sub.groupby(col).agg(**agg_kwargs).reset_index()
        g = g.sort_values("customers", ascending=False)
        total_customers = int(g["customers"].sum())
        out = []
        for r in g.to_dict("records"):
            rec = {
                col:         str(r[col]),
                "customers": int(r["customers"]),
                "orders":    int(r["orders"]),
                "cust_pct":  round(int(r["customers"]) / total_customers * 100, 2) if total_customers else 0.0,
            }
            if has_amt:
                rec["revenue"] = round(float(r["revenue"]), 2)
            out.append(rec)
        return out

    by_city    = _by("customer_city")
    by_region  = _by("region")
    by_country = _by("country")

    # Top entity summaries
    top_region  = (by_region or [None])[0]
    top_country = (by_country or [None])[0]
    top_city    = (by_city or [None])[0]

    return {
        "summary": {
            "n_customers":     n_customers,
            "n_unique_cities":    len(by_city) if by_city else 0,
            "n_unique_regions":   len(by_region) if by_region else 0,
            "n_unique_countries": len(by_country) if by_country else 0,
            "top_region":  top_region,
            "top_country": top_country,
            "top_city":    top_city,
        },
        "by_region":  by_region,
        "by_country": by_country,
        "by_city":    by_city[:50] if by_city else None,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_customers": 0,
            "n_unique_cities": 0, "n_unique_regions": 0, "n_unique_countries": 0,
            "top_region": None, "top_country": None, "top_city": None,
        },
        "by_region": None, "by_country": None, "by_city": None,
        "warning": warning,
    }
