"""A06 — Geographic Revenue Analysis.

Slices revenue, orders, customers, and AOV by geography. The module gracefully
degrades through the available hierarchy:

    country  →  region  →  customer_city

…with concentration metrics that flag whether revenue is "Pareto-heavy" (top
3 regions carry >70%) or evenly distributed.

Concentration metrics
---------------------
- **Top-N share**: % of total revenue from the top 1, 3, 5, 10 entities.
- **Herfindahl index** (HHI, 0–1 normalized): sum of squared shares.
  Lower = more diffuse market; higher = concentrated. Standard antitrust
  thresholds: <0.15 unconcentrated, 0.15–0.25 moderate, >0.25 concentrated.

Required columns:  region, total_amount
Optional columns:  net_amount, country, country_code, customer_city,
                   customer_id, order_date, latitude, longitude

Output schema::

    {
      "summary": {
        "total_revenue": float,
        "n_regions":   int,
        "n_countries": int,
        "n_cities":    int,
        "top_region":     {"name": str, "revenue": float, "pct": float},
        "top_country":    {...} | null,
        "top_3_share_pct":  float,
        "top_5_share_pct":  float,
        "top_10_share_pct": float,
        "herfindahl_index_region": float,   # 0..1
        "herfindahl_label":  "diffuse"|"moderate"|"concentrated"
      },
      "by_region":   [{"region": str, "revenue": float, "orders": int,
                       "customers": int, "aov": float, "pct": float, "rank": int}],
      "by_country":  [...],
      "by_city":     [...],            # top 20
      "region_trend": {"monthly": [...]},   # if order_date present
      "geo_points":  [{"lat": float, "lng": float, "revenue": float}],  # if lat/lng
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_money


QUESTION = "Where in the country are my orders coming from?"


def _herfindahl(shares_pct: pd.Series) -> float:
    """HHI normalized to [0, 1]. Input is percentage shares (0..100)."""
    fractions = shares_pct / 100.0
    return float((fractions ** 2).sum())


def _hhi_label(hhi: float) -> str:
    if hhi < 0.15:
        return "diffuse"
    if hhi < 0.25:
        return "moderate"
    return "concentrated"


def _agg_by(df: pd.DataFrame, by: str, total_rev: float,
            has_customer: bool) -> list[dict[str, Any]]:
    grouped = df.groupby(by)
    agg_dict = {"revenue": ("_revenue", "sum"), "orders": ("_revenue", "count")}
    if has_customer:
        agg_dict["customers"] = ("customer_id", "nunique")
    agg = grouped.agg(**agg_dict).reset_index()
    if not has_customer:
        agg["customers"] = 0
    agg["aov"] = (agg["revenue"] / agg["orders"]).round(2)
    agg["pct"] = (agg["revenue"] / total_rev * 100).round(2) if total_rev > 0 else 0.0
    agg = agg.sort_values("revenue", ascending=False).reset_index(drop=True)
    agg["rank"] = agg.index + 1
    return [
        {
            by: str(r[by]),
            "revenue": round(float(r["revenue"]), 2),
            "orders": int(r["orders"]),
            "customers": int(r["customers"]),
            "aov": float(r["aov"]),
            "pct": float(r["pct"]),
            "rank": int(r["rank"]),
        }
        for r in agg.to_dict("records")
    ]


@register(
    key="A06_geographic_revenue",
    analysis_type="revenue",
    required_cols=["region", "total_amount"],
    optional_cols=["net_amount", "country", "country_code", "customer_city",
                   "customer_id", "order_date", "latitude", "longitude"],
    description="Revenue by region/country/city with concentration metrics.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    revenue_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["region", revenue_col])
    df = df[df[revenue_col] >= 0]
    df["region"] = df["region"].astype(str)
    df["_revenue"] = df[revenue_col]

    if df.empty:
        return {
            **build_payload(
                question=QUESTION,
                headline=build_headline(value=0, label="regions with sales", period="no data"),
                fallback_bullets=[
                    "No region data yet — geographic analysis needs a region, city, or country column.",
                    "Once tagged, this card shows where your orders come from + which regions are most concentrated.",
                    "Use this to focus marketing on hot regions and discover untapped ones.",
                ],
                suggested_actions=[
                    action("Add region column", kind="primary",
                           deeplink="/dashboard/settings/data-sources", icon="arrow"),
                ],
            ),
            "summary": {
                "total_revenue": 0.0, "n_regions": 0, "n_countries": 0, "n_cities": 0,
                "top_region": None, "top_country": None,
                "top_3_share_pct": 0.0, "top_5_share_pct": 0.0, "top_10_share_pct": 0.0,
                "herfindahl_index_region": 0.0, "herfindahl_label": "diffuse",
            },
            "by_region": [], "by_country": [], "by_city": [],
            "region_trend": {"monthly": []}, "geo_points": [],
            "warning": "no rows with both region and revenue after coercion",
        }

    has_customer = has_col(df, "customer_id")
    if has_customer:
        df["customer_id"] = df["customer_id"].astype(str)
    total_rev = float(df["_revenue"].sum())

    # ── Region (always present) ─────────────────────────────────────────────
    by_region = _agg_by(df, "region", total_rev, has_customer)
    region_pcts = pd.Series([r["pct"] for r in by_region], dtype=float)
    hhi_region = _herfindahl(region_pcts)

    top_region = (
        {"name": by_region[0]["region"],
         "revenue": by_region[0]["revenue"],
         "pct": by_region[0]["pct"]}
        if by_region else None
    )

    def _top_n_share(rows: list[dict[str, Any]], n: int) -> float:
        return round(sum(r["pct"] for r in rows[:n]), 2)

    # ── Country ─────────────────────────────────────────────────────────────
    by_country: list[dict[str, Any]] = []
    n_countries = 0
    top_country = None
    if has_col(df, "country"):
        sub = df.dropna(subset=["country"]).copy()
        sub["country"] = sub["country"].astype(str)
        by_country = _agg_by(sub, "country", total_rev, has_customer)
        n_countries = len(by_country)
        if by_country:
            top_country = {"name": by_country[0]["country"],
                           "revenue": by_country[0]["revenue"],
                           "pct": by_country[0]["pct"]}

    # ── City (top 20) ───────────────────────────────────────────────────────
    by_city: list[dict[str, Any]] = []
    n_cities = 0
    if has_col(df, "customer_city"):
        sub = df.dropna(subset=["customer_city"]).copy()
        sub["customer_city"] = sub["customer_city"].astype(str)
        by_city_full = _agg_by(sub, "customer_city", total_rev, has_customer)
        n_cities = len(by_city_full)
        by_city = by_city_full[:20]

    # ── Region monthly trend ────────────────────────────────────────────────
    region_trend: dict[str, list[dict[str, Any]]] = {"monthly": []}
    if has_col(df, "order_date"):
        sub = df.copy()
        sub["order_date"] = coerce_date(sub["order_date"])
        sub = sub.dropna(subset=["order_date"])
        if not sub.empty:
            sub["_period"] = sub["order_date"].dt.to_period("M").astype(str)
            trend = (
                sub.groupby(["_period", "region"])["_revenue"].sum()
                   .reset_index().rename(columns={"_revenue": "revenue", "_period": "period"})
            )
            trend = trend.sort_values(["period", "region"])
            region_trend["monthly"] = [
                {"period": r["period"], "region": r["region"],
                 "revenue": round(float(r["revenue"]), 2)}
                for r in trend.to_dict("records")
            ]

    # ── Geo points (only if both lat & lng present) ─────────────────────────
    geo_points: list[dict[str, Any]] = []
    if has_col(df, "latitude") and has_col(df, "longitude"):
        sub = df.dropna(subset=["latitude", "longitude"]).copy()
        sub["latitude"] = coerce_numeric(sub["latitude"])
        sub["longitude"] = coerce_numeric(sub["longitude"])
        sub = sub.dropna(subset=["latitude", "longitude"])
        # Cluster by rounded lat/lng so the payload stays bounded on dense data.
        if not sub.empty:
            sub["_lat_r"] = sub["latitude"].round(2)
            sub["_lng_r"] = sub["longitude"].round(2)
            cluster = (
                sub.groupby(["_lat_r", "_lng_r"])["_revenue"].sum()
                   .reset_index().sort_values("_revenue", ascending=False).head(1000)
            )
            geo_points = [
                {"lat": float(r["_lat_r"]), "lng": float(r["_lng_r"]),
                 "revenue": round(float(r["_revenue"]), 2)}
                for r in cluster.to_dict("records")
            ]

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    top3_share = _top_n_share(by_region, 3)
    n_regions = int(len(by_region))
    hhi_label = _hhi_label(hhi_region)

    headline = build_headline(
        value=n_regions,
        label="regions with sales",
        period=f"{fmt_money(total_rev)} total",
    )

    bullets: list[str] = []
    if top_region:
        bullets.append(
            f"Top region: {top_region.get('name') or top_region.get('region')} — "
            f"{fmt_money(top_region.get('revenue', 0))} "
            f"({top_region.get('pct', 0):.1f}% of revenue)."
        )
    else:
        bullets.append(f"Sales spread across {n_regions} regions but no clear leader.")

    if top3_share >= 70:
        bullets.append(
            f"Highly concentrated: top 3 regions carry {top3_share:.0f}% of revenue. "
            f"Test marketing in adjacent regions to diversify."
        )
    elif top3_share >= 40:
        bullets.append(
            f"Moderate concentration: top 3 regions = {top3_share:.0f}% of revenue. "
            f"Healthy spread — double down on the top 3 for compounding returns."
        )
    else:
        bullets.append(
            f"Well-diversified across {n_regions} regions (HHI: {hhi_label}). "
            f"Focus on retaining the long tail."
        )

    if n_regions >= 10:
        bullets.append(
            "Run a per-region promo experiment — small budgets, fast feedback, "
            "find which region responds best per dollar spent."
        )
    else:
        bullets.append(
            "Expand geographic reach next — even one new region "
            "could meaningfully grow the business."
        )

    actions = [
        action("View geo map", kind="primary",
               deeplink="/dashboard/analytics?focus=A06", icon="arrow"),
        action("Export by-region CSV", kind="secondary", deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "total_revenue": round(total_rev, 2),
            "n_regions": int(len(by_region)),
            "n_countries": int(n_countries),
            "n_cities": int(n_cities),
            "top_region": top_region,
            "top_country": top_country,
            "top_3_share_pct": _top_n_share(by_region, 3),
            "top_5_share_pct": _top_n_share(by_region, 5),
            "top_10_share_pct": _top_n_share(by_region, 10),
            "herfindahl_index_region": round(hhi_region, 4),
            "herfindahl_label": _hhi_label(hhi_region),
        },
        "by_region": by_region,
        "by_country": by_country,
        "by_city": by_city,
        "region_trend": region_trend,
        "geo_points": geo_points,
        "warning": None,
    }
