"""A14 — Acquisition by Channel.

Answers the owner question:
    "Which marketing channel is bringing me the most customers?"

Splits customers and revenue by `acquisition_channel`, with three rankings
(by revenue, by AOV, by per-customer LTV) so a single number doesn't hide
trade-offs. Also tracks new-customer acquisition over time per channel.

Channel attribution rule
------------------------
Each customer is assigned the `acquisition_channel` value seen on their
*first* order (sorted by `order_date` if available, else first-row order).
This is the standard "first-touch" attribution. Subsequent orders inherit
that channel — even if the row's own value disagrees — so revenue is
attributed to the channel that brought the customer in.

Why per-customer LTV ranking matters
------------------------------------
A channel can win on revenue (just brings volume) but lose on LTV (low-value
customers). Surfacing both means a marketing lead can decide whether to
double down on volume or quality without us hiding the trade-off.

Required columns:  acquisition_channel, customer_id
Optional columns:  order_date, total_amount, net_amount, order_id,
                   customer_segment

Output schema (Decision-Chart v1 contract)::

    {
      # ── identity ─────────────────────────────────────────────────
      "question": str,                # frozen owner-voice question
      "headline": {                   # the big number on the card
        "value": float | int,
        "label": str,
        "trend_pct": float | None,
        "trend_direction": "up"|"down"|"flat"|None,
        "period": str
      },

      # ── analytics payload (unchanged) ────────────────────────────
      "summary": { ... },
      "by_channel": [ ... ],
      "monthly_acquisition": [...] | None,
      "channel_x_segment":   [...] | None,

      # ── decision support ─────────────────────────────────────────
      "fallback_bullets": [str, str, str],    # exactly 3 owner-voice bullets
      "suggested_actions": [
        {"label": str, "kind": "primary"|"secondary"|...,
         "deeplink": str|None, "icon": "arrow"|"download"|"more"|None}
      ],

      "warning": str | None
    }

The `question`, `headline`, `fallback_bullets`, and `suggested_actions`
fields are the contract every other module will follow once we propagate.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


QUESTION = "Which marketing channel is bringing me the most customers?"


def _herfindahl(shares_pct: pd.Series) -> float:
    """HHI normalized to [0, 1]. Input is percentage shares (0..100)."""
    fractions = shares_pct / 100.0
    return float((fractions ** 2).sum())


def _fmt_int(n: float | int) -> str:
    """Compact integer formatter — 1234 → '1,234', 12345 → '12.3k'."""
    n = int(n)
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if abs(n) >= 10_000:
        return f"{n/1_000:.1f}k"
    return f"{n:,}"


def _fmt_money(n: float | int) -> str:
    """USD formatter — 1234 → '$1.2k', 12345 → '$12.3k'."""
    n = float(n)
    if abs(n) >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"${n/1_000:.1f}k"
    return f"${n:.0f}"


def _compute_headline(
    n_customers: int,
    monthly_acq: list[dict] | None,
) -> dict:
    """Build the headline strip — value + trend vs prior period."""
    headline = {
        "value": n_customers,
        "label": "new customers",
        "trend_pct": None,
        "trend_direction": None,
        "period": "All time",
    }

    if monthly_acq:
        # Roll up to per-period totals (across all channels)
        per_period: dict[str, int] = {}
        for row in monthly_acq:
            p = str(row.get("period") or "")
            per_period[p] = per_period.get(p, 0) + int(row.get("new_customers") or 0)

        if len(per_period) >= 2:
            periods_sorted = sorted(per_period.keys())
            last, prev = periods_sorted[-1], periods_sorted[-2]
            last_v = per_period[last]
            prev_v = per_period[prev]
            if prev_v > 0:
                pct = round((last_v - prev_v) / prev_v * 100.0, 1)
                headline["value"] = last_v
                headline["trend_pct"] = pct
                headline["trend_direction"] = (
                    "up" if pct > 1 else "down" if pct < -1 else "flat"
                )
                headline["period"] = f"This month ({last})"

    return headline


def _build_bullets(summary: dict, by_channel: list[dict]) -> list[str]:
    """Deterministic 3-bullet fallback in owner voice.

    These get replaced by an LLM later. The shape (exactly 3 strings, each
    ≤140 chars) is the contract the LLM will follow.
    """
    bullets: list[str] = []

    best_rev = summary.get("best_channel_revenue")
    best_aov = summary.get("best_channel_aov")
    best_ltv = summary.get("best_channel_ltv")
    n_channels = int(summary.get("n_channels") or 0)
    concentration = float(summary.get("channel_concentration") or 0.0)

    # Bullet 1 — winner by revenue (always)
    if best_rev:
        bullets.append(
            f"{str(best_rev.get('name','—')).title()} is your strongest channel — "
            f"{best_rev.get('share_pct',0):.0f}% of revenue ({_fmt_money(best_rev.get('revenue',0))})."
        )

    # Bullet 2 — if a different channel wins on AOV, surface the trade-off
    if best_aov and best_rev and str(best_aov.get('name')) != str(best_rev.get('name')):
        bullets.append(
            f"{str(best_aov.get('name','—')).title()} brings higher-value orders "
            f"({_fmt_money(best_aov.get('aov',0))} AOV) — worth testing with more budget."
        )
    elif best_ltv and best_rev and str(best_ltv.get('name')) != str(best_rev.get('name')):
        bullets.append(
            f"{str(best_ltv.get('name','—')).title()} customers spend more over time "
            f"({_fmt_money(best_ltv.get('avg_ltv',0))} LTV) — best for long-term growth."
        )
    else:
        # Same channel wins everywhere — that's actually noteworthy
        bullets.append(
            f"{str((best_rev or {}).get('name','—')).title()} dominates on volume AND "
            f"per-customer value — your unfair advantage."
        )

    # Bullet 3 — concentration risk vs diversification opportunity
    if concentration >= 0.5:
        bullets.append(
            f"You're heavily concentrated in {n_channels} channel(s). Test 1 new "
            f"channel this month to reduce dependency risk."
        )
    elif concentration <= 0.25 and n_channels >= 3:
        bullets.append(
            f"Acquisition is well-diversified across {n_channels} channels — "
            f"focus budget on the top 2 for compounding returns."
        )
    else:
        # mid-range: suggest growth focus
        if best_rev:
            bullets.append(
                f"Increase {str(best_rev.get('name','—')).title()} spend by 20% next "
                f"month and watch CAC vs new-customer count."
            )
        else:
            bullets.append("Not enough acquisition data yet — keep collecting attribution.")

    # Enforce ≤140 chars per bullet
    return [b if len(b) <= 140 else (b[:137] + "…") for b in bullets[:3]]


def _build_actions(summary: dict) -> list[dict]:
    """2–3 suggested actions matched to the headline finding."""
    actions: list[dict] = []
    best_rev = summary.get("best_channel_revenue") or {}
    best_aov = summary.get("best_channel_aov") or {}
    best_name = str(best_rev.get("name") or "").lower()
    best_aov_name = str(best_aov.get("name") or "").lower()

    if best_name:
        actions.append({
            "label": f"Increase {best_name.title()} budget",
            "kind": "primary",
            "deeplink": f"/dashboard/forecasting?action=shift-budget&to={best_name}",
            "icon": "arrow",
        })

    if best_aov_name and best_aov_name != best_name:
        actions.append({
            "label": f"Test {best_aov_name.title()} with more spend",
            "kind": "secondary",
            "deeplink": f"/dashboard/forecasting?action=test-channel&channel={best_aov_name}",
            "icon": "arrow",
        })

    actions.append({
        "label": "Export channel report",
        "kind": "secondary",
        "deeplink": None,
        "icon": "download",
    })

    return actions[:3]


@register(
    key="A14_acquisition_channel",
    analysis_type="customer",
    required_cols=["acquisition_channel", "customer_id"],
    optional_cols=["order_date", "total_amount", "net_amount", "order_id",
                   "customer_segment"],
    description="Customer/revenue/AOV/LTV breakdown by acquisition channel.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["acquisition_channel", "customer_id"])
    df["acquisition_channel"] = df["acquisition_channel"].astype(str)
    df["customer_id"] = df["customer_id"].astype(str)

    has_revenue = False
    revenue_col = None
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
        revenue_col = "net_amount"
        has_revenue = True
    elif has_col(df, "total_amount"):
        df["total_amount"] = coerce_numeric(df["total_amount"])
        revenue_col = "total_amount"
        has_revenue = True

    if has_revenue:
        df["_revenue"] = df[revenue_col].fillna(0).clip(lower=0)
    else:
        df["_revenue"] = 0.0

    has_date = has_col(df, "order_date")
    if has_date:
        df["order_date"] = coerce_date(df["order_date"])

    if df.empty:
        return {
            "question": QUESTION,
            "headline": {
                "value": 0, "label": "new customers",
                "trend_pct": None, "trend_direction": None,
                "period": "no data",
            },
            "summary": {
                "n_customers": 0, "n_channels": 0, "total_revenue": 0.0,
                "best_channel_revenue": None, "best_channel_aov": None,
                "best_channel_ltv": None, "channel_concentration": 0.0,
            },
            "by_channel": [], "monthly_acquisition": None,
            "channel_x_segment": None,
            "fallback_bullets": [
                "No acquisition_channel data yet — once your channels are mapped, "
                "this card will rank them by revenue, AOV and LTV.",
                "Tip: tag every order's referring channel (organic / paid / direct / "
                "social / email) before the next upload.",
                "Without channel data, you can't measure CAC or know which spend "
                "actually pays back — start tracking now.",
            ],
            "suggested_actions": [
                {"label": "Learn how to tag channels", "kind": "primary",
                 "deeplink": "/dashboard/settings/data-sources", "icon": "arrow"},
            ],
            "warning": "no rows with both acquisition_channel and customer_id",
        }

    # ── First-touch attribution ─────────────────────────────────────────────
    # For each customer pick the channel from their first order. If no date
    # is available, take the first row encountered (input order is typically
    # already temporal in raw exports).
    if has_date:
        first_orders = (
            df.dropna(subset=["order_date"])
              .sort_values(["customer_id", "order_date"])
              .drop_duplicates(subset="customer_id", keep="first")
              [["customer_id", "acquisition_channel"]]
        )
    else:
        first_orders = (
            df.drop_duplicates(subset="customer_id", keep="first")
              [["customer_id", "acquisition_channel"]]
        )
    cust_channel = first_orders.set_index("customer_id")["acquisition_channel"]
    df["_first_touch_channel"] = df["customer_id"].map(cust_channel)
    # Customers that somehow lost mapping (NaN order_date everywhere) keep their
    # row-level channel as a fallback.
    df["_first_touch_channel"] = df["_first_touch_channel"].fillna(df["acquisition_channel"])

    n_customers = int(df["customer_id"].nunique())
    total_rev = float(df["_revenue"].sum())

    # ── Per-channel aggregation ─────────────────────────────────────────────
    agg_kwargs = {
        "customers": ("customer_id", "nunique"),
        "revenue": ("_revenue", "sum"),
    }
    if has_col(df, "order_id"):
        df["order_id"] = df["order_id"].astype(str)
        agg_kwargs["orders"] = ("order_id", "nunique")
    else:
        agg_kwargs["orders"] = ("_revenue", "count")

    chan = (
        df.groupby("_first_touch_channel").agg(**agg_kwargs).reset_index()
          .rename(columns={"_first_touch_channel": "channel"})
    )
    chan["aov"] = (chan["revenue"] / chan["orders"]).round(2)
    chan["avg_ltv"] = (chan["revenue"] / chan["customers"]).round(2)
    chan["rev_share_pct"] = (chan["revenue"] / total_rev * 100).round(2) if total_rev > 0 else 0.0
    chan["cust_share_pct"] = (chan["customers"] / n_customers * 100).round(2)
    chan = chan.sort_values("revenue", ascending=False).reset_index(drop=True)
    chan["rank"] = chan.index + 1

    by_channel = [
        {
            "channel": str(r["channel"]),
            "rank": int(r["rank"]),
            "customers": int(r["customers"]),
            "orders": int(r["orders"]),
            "revenue": round(float(r["revenue"]), 2),
            "aov": float(r["aov"]),
            "avg_ltv": float(r["avg_ltv"]),
            "rev_share_pct": float(r["rev_share_pct"]),
            "cust_share_pct": float(r["cust_share_pct"]),
        }
        for r in chan.to_dict("records")
    ]

    # ── Best-channel highlights ─────────────────────────────────────────────
    best_rev = by_channel[0] if by_channel else None
    best_aov_row = max(by_channel, key=lambda r: r["aov"], default=None)
    best_ltv_row = max(by_channel, key=lambda r: r["avg_ltv"], default=None)

    summary = {
        "n_customers": n_customers,
        "n_channels": int(len(by_channel)),
        "total_revenue": round(total_rev, 2),
        "best_channel_revenue": (
            {"name": best_rev["channel"], "revenue": best_rev["revenue"],
             "share_pct": best_rev["rev_share_pct"]} if best_rev else None
        ),
        "best_channel_aov": (
            {"name": best_aov_row["channel"], "aov": best_aov_row["aov"]}
            if best_aov_row else None
        ),
        "best_channel_ltv": (
            {"name": best_ltv_row["channel"], "avg_ltv": best_ltv_row["avg_ltv"]}
            if best_ltv_row else None
        ),
        "channel_concentration": round(
            _herfindahl(chan["cust_share_pct"]), 4
        ),
    }

    # ── New customers per channel per month ─────────────────────────────────
    monthly_acquisition = None
    if has_date:
        first_with_date = (
            df.dropna(subset=["order_date"])
              .sort_values(["customer_id", "order_date"])
              .drop_duplicates(subset="customer_id", keep="first")
        )
        if not first_with_date.empty:
            first_with_date = first_with_date.copy()
            first_with_date["_period"] = first_with_date["order_date"].dt.to_period("M").astype(str)
            counts = (
                first_with_date.groupby(["_period", "acquisition_channel"])
                               .size().reset_index(name="new_customers")
                               .rename(columns={"acquisition_channel": "channel"})
            )
            counts = counts.sort_values(["_period", "channel"])
            monthly_acquisition = [
                {"period": str(r["_period"]), "channel": str(r["channel"]),
                 "new_customers": int(r["new_customers"])}
                for r in counts.to_dict("records")
            ]

    # ── Channel × segment matrix ────────────────────────────────────────────
    channel_x_segment = None
    if has_col(df, "customer_segment"):
        sub = df.dropna(subset=["customer_segment"]).copy()
        if not sub.empty:
            sub["customer_segment"] = sub["customer_segment"].astype(str)
            seg = (
                sub.drop_duplicates(subset=["customer_id"])
                   .groupby(["_first_touch_channel", "customer_segment"])
                   .size().reset_index(name="customers")
                   .rename(columns={"_first_touch_channel": "channel",
                                    "customer_segment": "segment"})
                   .sort_values(["channel", "customers"], ascending=[True, False])
            )
            channel_x_segment = [
                {"channel": str(r["channel"]), "segment": str(r["segment"]),
                 "customers": int(r["customers"])}
                for r in seg.to_dict("records")
            ]

    # ── Decision-Chart contract (v1) ────────────────────────────────────────
    headline = _compute_headline(n_customers, monthly_acquisition)
    fallback_bullets = _build_bullets(summary, by_channel)
    suggested_actions = _build_actions(summary)

    return {
        "question": QUESTION,
        "headline": headline,
        "summary": summary,
        "by_channel": by_channel,
        "monthly_acquisition": monthly_acquisition,
        "channel_x_segment": channel_x_segment,
        "fallback_bullets": fallback_bullets,
        "suggested_actions": suggested_actions,
        "warning": None,
    }
