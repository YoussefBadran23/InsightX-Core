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
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "Where are my customers concentrated on the map?"


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

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    n_regions = len(by_region) if by_region else 0
    n_cities = len(by_city) if by_city else 0
    n_countries = len(by_country) if by_country else 0
    headline = build_headline(
        value=n_regions or n_countries or n_cities,
        label="regions with customers" if n_regions else ("cities with customers" if n_cities else "countries"),
        period=f"{fmt_int(n_customers)} customers",
    )

    bullets: list[str] = []
    if top_region:
        bullets.append(
            f"Top region: {top_region.get('region') or top_region.get('name')} — "
            f"{int(top_region.get('count', 0)):,} customers "
            f"({top_region.get('pct', 0):.1f}%)."
        )
    elif top_country:
        bullets.append(
            f"Top country: {top_country.get('country') or top_country.get('name')} — "
            f"{int(top_country.get('count', 0)):,} customers."
        )
    else:
        bullets.append(f"Customers spread across {n_regions or n_countries or n_cities} locations.")

    if n_regions >= 10:
        bullets.append(
            f"Broad geographic spread across {n_regions} regions — "
            f"opportunity to localise marketing per region."
        )
    elif n_regions >= 3:
        bullets.append(
            f"Customers focused in {n_regions} regions — "
            f"deepen presence in each before expanding."
        )
    else:
        bullets.append(
            "Customer base is geographically concentrated — "
            "consider testing one new region for organic expansion."
        )

    if top_city:
        bullets.append(
            f"Top city: {top_city.get('city') or top_city.get('name')} with "
            f"{int(top_city.get('count', 0)):,} customers — your local-hero market."
        )
    else:
        bullets.append(
            "Add a city column to your customer data for granular geo targeting."
        )

    actions = [
        action("View geo map", kind="primary",
               deeplink="/dashboard/analytics?focus=C03", icon="arrow"),
        action("Export geo CSV", kind="secondary", deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
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
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="regions with customers", period="no data"),
            fallback_bullets=[
                "No geographic data yet — add region, city, or country columns to your customer data.",
                "Once tagged, this card pinpoints where customers concentrate on a map.",
                "Geographic targeting is one of the highest-ROI marketing levers — start tracking now.",
            ],
            suggested_actions=[
                action("Add geo columns", kind="primary",
                       deeplink="/dashboard/settings/data-sources", icon="arrow"),
            ],
        ),
        "summary": {
            "n_customers": 0,
            "n_unique_cities": 0, "n_unique_regions": 0, "n_unique_countries": 0,
            "top_region": None, "top_country": None, "top_city": None,
        },
        "by_region": None, "by_country": None, "by_city": None,
        "warning": warning,
    }
