"""A01 — Revenue Summary.

Computes total revenue, daily/weekly/monthly aggregations, and breakdowns
by region and currency. The primary revenue figure prefers `net_amount` if
available (already discount-adjusted), otherwise falls back to `total_amount`.

Required columns:  total_amount, order_date
Optional columns:  net_amount, region, currency, discount_amount

Output schema::

    {
      "summary": {
        "total":       float,
        "avg_daily":   float,
        "avg_weekly":  float,
        "avg_monthly": float,
        "order_count": int,
        "date_range":  {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "n_days": int}
      },
      "by_period": {
        "daily":   [{"date": "YYYY-MM-DD", "revenue": float, "orders": int}],
        "weekly":  [{"period": "YYYY-Wnn",  "revenue": float, "orders": int}],
        "monthly": [{"period": "YYYY-MM",   "revenue": float, "orders": int}]
      },
      "by_region":   [{"region": str,   "revenue": float, "pct": float}],
      "by_currency": [{"currency": str, "revenue": float, "pct": float}],
      "top_days":    [{"date": "YYYY-MM-DD", "revenue": float}],   # 10 largest
      "discount_summary": {                                          # if discount_amount present
        "total_discount":   float,
        "discount_pct":     float,
        "orders_with_disc": int
      },
      "period_comparison": {                                         # added
        "buckets": [{"label": "Mar 2018", "month": "2018-03",
                      "current": float, "previous": float|null}],
        "current_total":  float,
        "previous_total": float,
        "change_pct":     float|null,
        "current_range":  {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
        "previous_range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
      }
    }
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_money


QUESTION = "How much money did I make, and is it more or less than before?"


@register(
    key="A01_revenue_summary",
    analysis_type="revenue",
    required_cols=["total_amount", "order_date"],
    optional_cols=["net_amount", "region", "currency", "discount_amount"],
    description="Total revenue breakdown by region, period, and category.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()

    # Coerce types defensively. The seed CSVs may carry currency symbols on
    # `total_amount` (variant 03_bad_types) and mixed date formats.
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["order_date", amount_col])

    # Drop sub-zero noise so anomaly modules can flag negatives separately
    # instead of having the headline revenue silently shrink. We keep zeros.
    df = df[df[amount_col] >= 0]

    if df.empty:
        return {
            **build_payload(
                question=QUESTION,
                headline=build_headline(
                    value=0, label="revenue (no data)", period="no data",
                ),
                fallback_bullets=[
                    "No completed orders found yet — upload sales data with "
                    "order_date and total_amount columns to populate this chart.",
                    "Once data lands, this card shows total revenue + trend vs "
                    "the prior 6 months side-by-side.",
                    "Tip: cleaner CSVs (ISO dates, numeric amounts) yield faster "
                    "and more accurate analytics.",
                ],
                suggested_actions=[
                    action("Upload data", kind="primary",
                           deeplink="/dashboard/upload", icon="arrow"),
                ],
            ),
            "summary": {
                "total": 0.0, "avg_daily": 0.0, "avg_weekly": 0.0,
                "avg_monthly": 0.0, "order_count": 0,
                "date_range": {"start": None, "end": None, "n_days": 0},
            },
            "by_period": {"daily": [], "weekly": [], "monthly": []},
            "by_region": [], "by_currency": [], "top_days": [],
            "discount_summary": None,
            "period_comparison": {
                "buckets": [], "current_total": 0.0, "previous_total": 0.0,
                "change_pct": None,
                "current_range": {"start": None, "end": None},
                "previous_range": {"start": None, "end": None},
            },
        }

    total = float(df[amount_col].sum())
    date_min, date_max = df["order_date"].min(), df["order_date"].max()
    n_days = max((date_max - date_min).days + 1, 1)

    # ── Aggregations ────────────────────────────────────────────────────────
    daily = (
        df.groupby(df["order_date"].dt.date)
          .agg(revenue=(amount_col, "sum"), orders=(amount_col, "count"))
          .reset_index().rename(columns={"order_date": "date"})
          .sort_values("date")
    )
    weekly = (
        df.groupby(df["order_date"].dt.to_period("W"))
          .agg(revenue=(amount_col, "sum"), orders=(amount_col, "count"))
          .reset_index().rename(columns={"order_date": "period"})
    )
    weekly["period"] = weekly["period"].astype(str)
    monthly = (
        df.groupby(df["order_date"].dt.to_period("M"))
          .agg(revenue=(amount_col, "sum"), orders=(amount_col, "count"))
          .reset_index().rename(columns={"order_date": "period"})
    )
    monthly["period"] = monthly["period"].astype(str)

    # ── Categorical breakdowns ──────────────────────────────────────────────
    breakdowns: dict[str, list] = {}
    for col in ("region", "currency"):
        if has_col(df, col):
            agg = (
                df.groupby(col)[amount_col].sum()
                  .reset_index().rename(columns={amount_col: "revenue"})
            )
            agg["pct"] = (agg["revenue"] / total * 100).round(2)
            breakdowns[col] = agg.sort_values("revenue", ascending=False).to_dict("records")

    # ── Period comparison (last 6 calendar months vs the 6 prior) ──────────
    # Drives the "Revenue Trends" chart on the home dashboard. Anchors at the
    # LATEST data month (not today) so re-uploaded historical data still has
    # a meaningful "current" view. If the dataset is short we shrink the
    # window down so we always emit something usable instead of empty arrays.
    last_period = monthly["period"].iloc[-1] if len(monthly) > 0 else None
    period_comparison: dict[str, Any] = {
        "buckets": [], "current_total": 0.0, "previous_total": 0.0,
        "change_pct": None,
        "current_range": {"start": None, "end": None},
        "previous_range": {"start": None, "end": None},
    }
    if last_period is not None:
        window = min(6, max(1, len(monthly)))            # 1..6 buckets
        # Build a complete sequence of months ending at last_period so even
        # months with zero revenue render as a bucket (no gappy line chart).
        last_pp = pd.Period(last_period, freq="M")
        cur_months = [last_pp - i for i in range(window - 1, -1, -1)]
        prev_months = [last_pp - window - i for i in range(window - 1, -1, -1)]
        # Map periods → revenue from the monthly aggregation we already have.
        rev_by_period: dict[str, float] = {
            r["period"]: float(r["revenue"]) for r in monthly.to_dict("records")
        }
        buckets = []
        for cur, prev in zip(cur_months, prev_months):
            cur_str, prev_str = str(cur), str(prev)
            buckets.append({
                "label": cur.strftime("%b %Y"),
                "month": cur_str,
                "current":  round(rev_by_period.get(cur_str, 0.0), 2),
                "previous": round(rev_by_period.get(prev_str, 0.0), 2)
                            if prev_str in rev_by_period else None,
            })
        cur_total = sum(b["current"] for b in buckets)
        prev_total = sum((b["previous"] or 0.0) for b in buckets)
        change_pct = (
            round(((cur_total - prev_total) / prev_total) * 100, 2)
            if prev_total > 0 else None
        )
        period_comparison = {
            "buckets": buckets,
            "current_total":  round(cur_total, 2),
            "previous_total": round(prev_total, 2),
            "change_pct": change_pct,
            "current_range": {
                "start": cur_months[0].start_time.date().isoformat(),
                "end":   cur_months[-1].end_time.date().isoformat(),
            },
            "previous_range": {
                "start": prev_months[0].start_time.date().isoformat(),
                "end":   prev_months[-1].end_time.date().isoformat(),
            },
        }

    # ── Optional discount summary ───────────────────────────────────────────
    discount_summary = None
    if has_col(df, "discount_amount"):
        df["discount_amount"] = coerce_numeric(df["discount_amount"]).fillna(0)
        total_disc = float(df["discount_amount"].sum())
        gross = float(df["total_amount"].sum())
        discount_summary = {
            "total_discount": round(total_disc, 2),
            "discount_pct": round(100 * total_disc / gross, 2) if gross > 0 else 0.0,
            "orders_with_disc": int((df["discount_amount"] > 0).sum()),
        }

    # ── Decision-Chart v1 contract fields ──────────────────────────────────
    # Headline: prefer the period-comparison's current_total (better signal
    # than the all-time total because users care about "this period vs last").
    pc = period_comparison
    pc_change_pct = pc.get("change_pct")
    headline = build_headline(
        value=round(pc.get("current_total") or total, 2),
        label="revenue · current period",
        trend_pct=pc_change_pct,
        period=(
            f"Last {min(6, max(1, len(monthly)))} months"
            if last_period is not None else "All time"
        ),
    )

    # Bullets — owner-voice, derived from the data:
    bullets: list[str] = []
    # 1 — Headline trend statement
    if pc_change_pct is not None:
        if pc_change_pct >= 1:
            bullets.append(
                f"You earned {fmt_money(pc['current_total'])} this period — "
                f"up {pc_change_pct:.1f}% vs the previous {len(pc['buckets'])} months."
            )
        elif pc_change_pct <= -1:
            bullets.append(
                f"You earned {fmt_money(pc['current_total'])} this period — "
                f"down {abs(pc_change_pct):.1f}% vs the previous {len(pc['buckets'])} months."
            )
        else:
            bullets.append(
                f"Revenue this period is roughly flat at "
                f"{fmt_money(pc['current_total'])} ({pc_change_pct:+.1f}%)."
            )
    else:
        bullets.append(
            f"Total revenue: {fmt_money(total)} across {int(len(df)):,} orders."
        )
    # 2 — Best day
    if not daily.empty:
        top_row = daily.nlargest(1, "revenue").iloc[0]
        bullets.append(
            f"Your strongest day was {top_row['date']} with "
            f"{fmt_money(top_row['revenue'])} in revenue."
        )
    # 3 — Per-day average + actionable framing
    avg_daily = total / n_days
    if pc_change_pct is not None and pc_change_pct <= -5:
        bullets.append(
            f"Average is {fmt_money(avg_daily)}/day. Trend is down — investigate "
            f"top products and check stockouts."
        )
    elif pc_change_pct is not None and pc_change_pct >= 10:
        bullets.append(
            f"Average is {fmt_money(avg_daily)}/day. Strong growth — "
            f"double down on what's working before momentum cools."
        )
    else:
        bullets.append(
            f"You average {fmt_money(avg_daily)} per day — set a 7-day target "
            f"and review weekly to spot drift early."
        )

    # Actions
    actions = [
        action("Drill into top days", kind="primary",
               deeplink="/dashboard/analytics?focus=A01", icon="arrow"),
        action("Export revenue CSV", kind="secondary",
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
            "total": round(total, 2),
            "avg_daily": round(total / n_days, 2),
            "avg_weekly": round(total / max(len(weekly), 1), 2),
            "avg_monthly": round(total / max(len(monthly), 1), 2),
            "order_count": int(len(df)),
            "date_range": {
                "start": date_min.date().isoformat(),
                "end": date_max.date().isoformat(),
                "n_days": int(n_days),
            },
        },
        "by_period": {
            "daily":   [{"date": str(r["date"]), "revenue": round(r["revenue"], 2), "orders": int(r["orders"])}
                        for r in daily.to_dict("records")],
            "weekly":  [{"period": r["period"], "revenue": round(r["revenue"], 2), "orders": int(r["orders"])}
                        for r in weekly.to_dict("records")],
            "monthly": [{"period": r["period"], "revenue": round(r["revenue"], 2), "orders": int(r["orders"])}
                        for r in monthly.to_dict("records")],
        },
        "by_region":   breakdowns.get("region", []),
        "by_currency": breakdowns.get("currency", []),
        "top_days":    [{"date": str(r["date"]), "revenue": round(r["revenue"], 2)}
                        for r in daily.nlargest(10, "revenue").to_dict("records")],
        "discount_summary": discount_summary,
        "period_comparison": period_comparison,
    }
