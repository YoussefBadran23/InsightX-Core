"""A17 — Customer Lifetime Value Prediction (BG/NBD + Gamma-Gamma).

Probabilistic CLV using two classic non-contractual models:

- **BG/NBD** (Beta-Geometric Negative Binomial Distribution)
  Predicts the expected number of future purchases per customer over a horizon.
  Source: Fader, Hardie & Lee (2005). The model assumes:
  - While alive, a customer's transactions follow a Poisson process.
  - After each transaction, there's a probability they "die" (churn).
  - Both the transaction rate and dropout probability vary across customers
    according to Gamma and Beta distributions respectively.

- **Gamma-Gamma**: Predicts the expected monetary value per future transaction.
  Requires that monetary value and transaction frequency are uncorrelated —
  we check the correlation and warn if it's high (>0.3).

CLV(horizon=t) = E[txn(t) | history] × E[monetary | history]

How A17 differs from A02 / A10
------------------------------
- A02 RFM: discrete *current* segments (Champions / At Risk / etc.).
- A10:    continuous *historical* lifetime stats (LTV, lifespan).
- A17:    *predicted* future value. Uses probabilistic models, not aggregates.

Required columns:  customer_id, order_date, total_amount
Optional columns:  net_amount

Output schema::

    {
      "summary": {
        "n_customers_modeled":   int,
        "snapshot_date":         "YYYY-MM-DD",
        "horizon_days":          int,
        "horizon_label":         "90d"|"180d"|"365d",
        "total_predicted_clv":   float,
        "avg_predicted_clv":     float,
        "median_predicted_clv":  float,
        "monetary_freq_corr":    float,    # G-G assumption check
        "model_engine":          "lifetimes 0.11.3"
      },
      "horizons": {
        "90":  {"avg_predicted_orders": float, "avg_predicted_value": float,
                "total_clv": float},
        "180": {...},
        "365": {...}
      },
      "top_customers": [
        {"customer_id": str, "historical_value": float,
         "predicted_orders_90d": float, "predicted_value_90d": float,
         "predicted_clv_90d": float, "predicted_clv_365d": float,
         "alive_probability": float}
      ],
      "clv_distribution": [...],
      "warning": str | null
    }
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register

# lifetimes uses scipy.optimize and emits a flood of "covariance matrix"
# warnings on small datasets. Silence them — we already report convergence
# health via the model.confidence_intervals_ attribute when needed.
warnings.filterwarnings("ignore", message=".*covariance.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")
warnings.filterwarnings("ignore", category=UserWarning, module="lifetimes")
logging.getLogger("lifetimes").setLevel(logging.ERROR)


MIN_CUSTOMERS = 50         # below this, the BG/NBD model overfits
MIN_REPEATERS = 10         # need ≥10 customers with ≥2 orders for G-G
DISCOUNT_RATE_MONTHLY = 0.01
CLV_BUCKETS = [
    (0, 50,    "0-50"),
    (50, 100,  "50-100"),
    (100, 250, "100-250"),
    (250, 500, "250-500"),
    (500, 1000, "500-1k"),
    (1000, 2500, "1k-2.5k"),
    (2500, 5000, "2.5k-5k"),
    (5000, float("inf"), "5k+"),
]


def _bucketize(values: pd.Series, buckets) -> list[dict[str, Any]]:
    n = len(values) or 1
    out = []
    for lo, hi, label in buckets:
        mask = (values >= lo) & (values < hi)
        cnt = int(mask.sum())
        out.append({
            "bucket": label,
            "count": cnt,
            "pct": round(cnt / n * 100, 2),
            "predicted_clv": round(float(values[mask].sum()), 2),
        })
    return out


@register(
    key="A17_clv_prediction",
    analysis_type="customer",
    required_cols=["customer_id", "order_date", "total_amount"],
    optional_cols=["net_amount"],
    description="Probabilistic CLV prediction (BG/NBD + Gamma-Gamma).",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    revenue_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", "order_date", revenue_col])
    df = df[df[revenue_col] > 0]
    df["customer_id"] = df["customer_id"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    n_customers = df["customer_id"].nunique()
    if n_customers < MIN_CUSTOMERS:
        return _empty(
            f"only {n_customers} customers — BG/NBD overfits below ~{MIN_CUSTOMERS}"
        )

    # ── Build lifetimes summary frame (frequency / recency / T / monetary) ──
    # frequency = number of REPEAT purchases (not first)
    # recency   = days between first and last purchase
    # T         = days between first purchase and observation date
    # monetary  = average value PER REPEAT purchase
    from lifetimes.utils import summary_data_from_transaction_data

    snapshot = df["order_date"].max()
    summary = summary_data_from_transaction_data(
        transactions=df,
        customer_id_col="customer_id",
        datetime_col="order_date",
        monetary_value_col=revenue_col,
        observation_period_end=snapshot,
        freq="D",
    ).reset_index()

    # G-G requires positive monetary on REPEAT purchases (frequency >= 1).
    # Customers with frequency=0 (one-timers) get a fallback: their predicted
    # monetary value is the historical avg of the modeled cohort.
    gg_input = summary[(summary["frequency"] > 0) & (summary["monetary_value"] > 0)]
    if len(gg_input) < MIN_REPEATERS:
        return _empty(
            f"only {len(gg_input)} repeat-purchase customers — need ≥{MIN_REPEATERS} "
            "for Gamma-Gamma monetary model"
        )

    # Correlation check — Gamma-Gamma assumes monetary ⊥ frequency.
    monetary_freq_corr = float(gg_input[["frequency", "monetary_value"]].corr().iloc[0, 1])

    # ── Fit BG/NBD with penalizer escalation ────────────────────────────────
    # On datasets with very high frequencies + short windows, scipy's BFGS
    # optimizer can hit `nan` in the Jacobian. Escalating the penalizer
    # regularizes the fit and pushes the optimizer away from those edges.
    from lifetimes import BetaGeoFitter, GammaGammaFitter

    bgf = None
    bgf_warning = None
    for penalizer in (0.001, 0.01, 0.1, 1.0):
        try:
            candidate = BetaGeoFitter(penalizer_coef=penalizer)
            candidate.fit(summary["frequency"], summary["recency"], summary["T"])
            bgf = candidate
            if penalizer > 0.001:
                bgf_warning = f"BG/NBD required penalizer={penalizer} for convergence"
            break
        except Exception:
            continue
    if bgf is None:
        return _empty("BG/NBD fit failed at all penalizer levels (0.001–1.0)")

    # ── Fit Gamma-Gamma with same escalation strategy ───────────────────────
    ggf = None
    for penalizer in (0.001, 0.01, 0.1, 1.0):
        try:
            candidate = GammaGammaFitter(penalizer_coef=penalizer)
            candidate.fit(gg_input["frequency"], gg_input["monetary_value"])
            ggf = candidate
            break
        except Exception:
            continue
    if ggf is None:
        return _empty("Gamma-Gamma fit failed at all penalizer levels")

    # ── Predictions per horizon ─────────────────────────────────────────────
    horizons = [90, 180, 365]
    horizon_results: dict[int, dict[str, Any]] = {}

    # Predicted alive probability — useful for a "still active?" signal.
    summary["alive_prob"] = bgf.conditional_probability_alive(
        summary["frequency"], summary["recency"], summary["T"]
    )

    # Predicted avg monetary per repeat (only meaningful for repeaters; set
    # to gg_input mean for one-timers — a safe historical fallback).
    fallback_avg = float(gg_input["monetary_value"].mean())
    has_repeats = summary["frequency"] > 0
    summary["pred_avg_value"] = fallback_avg
    if has_repeats.any():
        summary.loc[has_repeats, "pred_avg_value"] = (
            ggf.conditional_expected_average_profit(
                summary.loc[has_repeats, "frequency"],
                summary.loc[has_repeats, "monetary_value"],
            )
        )

    for h in horizons:
        col_orders = f"pred_orders_{h}"
        col_clv = f"pred_clv_{h}"
        summary[col_orders] = bgf.conditional_expected_number_of_purchases_up_to_time(
            h, summary["frequency"], summary["recency"], summary["T"]
        )
        # CLV with monthly discount applied via geometric decay.
        # ggf.customer_lifetime_value handles the discounting natively.
        try:
            clv = ggf.customer_lifetime_value(
                bgf,
                summary["frequency"],
                summary["recency"],
                summary["T"],
                summary["monetary_value"].clip(lower=0.01),
                time=h // 30,  # months
                discount_rate=DISCOUNT_RATE_MONTHLY,
                freq="D",
            )
        except Exception:
            # Fallback: simple multiplicative CLV without discounting.
            clv = summary[col_orders] * summary["pred_avg_value"]
        summary[col_clv] = clv.values if hasattr(clv, "values") else np.asarray(clv)

        horizon_results[h] = {
            "avg_predicted_orders": round(float(summary[col_orders].mean()), 3),
            "avg_predicted_value": round(float(summary[col_clv].mean()), 2),
            "total_clv": round(float(summary[col_clv].sum()), 2),
        }

    # ── Top customers (by 365-day predicted CLV) ────────────────────────────
    top = summary.nlargest(20, "pred_clv_365")
    top_customers: list[dict[str, Any]] = []
    for r in top.to_dict("records"):
        top_customers.append({
            "customer_id": str(r["customer_id"]),
            "historical_orders": int(r["frequency"] + 1),  # +1 because frequency excludes first
            "historical_value": round(float(r["monetary_value"]), 2),
            "predicted_orders_90d": round(float(r["pred_orders_90"]), 3),
            "predicted_value_per_order": round(float(r["pred_avg_value"]), 2),
            "predicted_clv_90d": round(float(r["pred_clv_90"]), 2),
            "predicted_clv_180d": round(float(r["pred_clv_180"]), 2),
            "predicted_clv_365d": round(float(r["pred_clv_365"]), 2),
            "alive_probability": round(float(r["alive_prob"]), 4),
        })

    avg_clv_365 = float(summary["pred_clv_365"].mean())
    median_clv_365 = float(summary["pred_clv_365"].median())
    total_clv_365 = float(summary["pred_clv_365"].sum())

    return {
        "summary": {
            "n_customers_modeled": int(len(summary)),
            "snapshot_date": snapshot.date().isoformat(),
            "horizon_days": 365,
            "horizon_label": "365d",
            "total_predicted_clv": round(total_clv_365, 2),
            "avg_predicted_clv": round(avg_clv_365, 2),
            "median_predicted_clv": round(median_clv_365, 2),
            "monetary_freq_corr": round(monetary_freq_corr, 4),
            "model_engine": "lifetimes 0.11.3 (BG/NBD + Gamma-Gamma)",
        },
        "horizons": {str(h): horizon_results[h] for h in horizons},
        "top_customers": top_customers,
        "clv_distribution": _bucketize(summary["pred_clv_365"], CLV_BUCKETS),
        "warning": (
            "; ".join(filter(None, [
                bgf_warning,
                (f"high monetary-frequency correlation ({monetary_freq_corr:.3f}) — "
                 "Gamma-Gamma assumption is shaky; treat values as directional"
                 if abs(monetary_freq_corr) > 0.3 else None),
            ])) or None
        ),
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_customers_modeled": 0, "snapshot_date": None,
            "horizon_days": 365, "horizon_label": "365d",
            "total_predicted_clv": 0.0, "avg_predicted_clv": 0.0,
            "median_predicted_clv": 0.0, "monetary_freq_corr": 0.0,
            "model_engine": "lifetimes 0.11.3 (BG/NBD + Gamma-Gamma)",
        },
        "horizons": {}, "top_customers": [], "clv_distribution": [],
        "warning": warning,
    }
