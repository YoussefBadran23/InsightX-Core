"""A17 — CLV Prediction (BG/NBD + Gamma-Gamma).

Primary: BG/NBD (purchase frequency) + Gamma-Gamma (monetary value) from
         the lifetimes library with penalizer tuning.
Fallback: Weighted heuristic using frequency, monetary, and recency decay.
Updates customers.clv_predicted.
"""

import pandas as pd
import numpy as np
from sqlalchemy import text
from ._base import analytics_task, has_col

try:
    from lifetimes import BetaGeoFitter, GammaGammaFitter
    from lifetimes.utils import summary_data_from_transaction_data
    _HAS_LIFETIMES = True
except ImportError:
    _HAS_LIFETIMES = False


def _fallback_clv(df, amount_col):
    """Improved heuristic CLV with recency decay and frequency weighting.

    CLV = avg_order_value * projected_annual_orders * recency_decay
    - projected_annual_orders: annualised from observed purchase rate
    - recency_decay: exponential decay based on days since last purchase
      (recent buyers are more likely to buy again)
    """
    ref_date = df["created_at"].max() + pd.Timedelta(days=1)

    cust = df.groupby("customer_id").agg(
        total_spend=(amount_col, "sum"),
        n_orders=(amount_col, "count"),
        first_order=("created_at", "min"),
        last_order=("created_at", "max"),
    ).reset_index()

    cust["avg_order_value"] = cust["total_spend"] / cust["n_orders"]
    cust["tenure_days"] = (ref_date - cust["first_order"]).dt.days.clip(lower=1)
    cust["recency_days"] = (ref_date - cust["last_order"]).dt.days

    # Annualised order rate (capped at observed frequency for single-purchase customers)
    cust["orders_per_year"] = np.where(
        cust["n_orders"] >= 2,
        cust["n_orders"] / cust["tenure_days"] * 365,
        cust["n_orders"] * 1.0,  # single order = no annual projection
    )

    # Recency decay: half-life of 90 days
    # Customers who bought recently get full weight; dormant ones decay
    half_life = 90
    cust["recency_decay"] = np.exp(-0.693 * cust["recency_days"] / half_life)

    # Frequency confidence: more orders = more reliable estimate
    cust["freq_weight"] = np.log1p(cust["n_orders"]) / np.log1p(cust["n_orders"].max())

    # CLV = avg_order * annual_rate * decay * horizon (1 year)
    cust["clv_predicted"] = (
        cust["avg_order_value"]
        * cust["orders_per_year"]
        * cust["recency_decay"]
        * (0.5 + 0.5 * cust["freq_weight"])  # blend: 50% base + 50% freq-weighted
    ).round(2)

    return cust


@analytics_task("A17_clv_prediction", "clv")
def run_clv_prediction(df, session, job_id):
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", "created_at", amount_col])
    df = df[df[amount_col] > 0]

    if len(df) < 10:
        return {
            "clv_summary": {},
            "top_customers": [],
            "summary": "Not enough transaction data for CLV prediction",
        }

    if not _HAS_LIFETIMES:
        cust = _fallback_clv(df, amount_col)
        for _, row in cust.iterrows():
            session.execute(
                text("UPDATE customers SET clv_predicted = :clv, updated_at = NOW() WHERE external_id = :cid"),
                {"clv": float(row["clv_predicted"]), "cid": row["customer_id"]},
            )
        session.commit()

        top = cust.nlargest(20, "clv_predicted")[
            ["customer_id", "clv_predicted", "total_spend", "n_orders", "recency_days"]
        ]
        return {
            "method": "heuristic_weighted",
            "clv_summary": {
                "mean": round(float(cust["clv_predicted"].mean()), 2),
                "median": round(float(cust["clv_predicted"].median()), 2),
                "p75": round(float(cust["clv_predicted"].quantile(0.75)), 2),
                "p90": round(float(cust["clv_predicted"].quantile(0.90)), 2),
                "total": round(float(cust["clv_predicted"].sum()), 2),
            },
            "top_customers": top.to_dict("records"),
            "total_customers": len(cust),
        }

    # ── BG/NBD + Gamma-Gamma (lifetimes library) ───────────────────────
    summary = summary_data_from_transaction_data(
        df,
        customer_id_col="customer_id",
        datetime_col="created_at",
        monetary_value_col=amount_col,
    )
    summary = summary[summary["frequency"] > 0]

    if len(summary) < 5:
        cust = _fallback_clv(df, amount_col)
        top = cust.nlargest(20, "clv_predicted")
        return {
            "method": "heuristic_weighted",
            "clv_summary": {"mean": round(float(cust["clv_predicted"].mean()), 2)},
            "top_customers": top[["customer_id", "clv_predicted"]].to_dict("records"),
            "total_customers": len(cust),
        }

    # Tune penalizer: try a few values, pick best by log-likelihood
    best_bgf = None
    best_ll = -np.inf
    for pen in [0.001, 0.01, 0.1]:
        try:
            bgf = BetaGeoFitter(penalizer_coef=pen)
            bgf.fit(summary["frequency"], summary["recency"], summary["T"])
            if bgf.summary is not None:
                # Use actual log-likelihood for model selection
                # log_likelihood_ is the total observed log-likelihood
                ll = getattr(bgf, "log_likelihood_", None)
                if ll is None:
                    # Fallback for older lifetimes versions: use negative AIC proxy
                    n_params = len(bgf.summary)
                    ll = -2 * bgf.summary["coef"].abs().sum() - 2 * n_params
                if ll > best_ll:
                    best_ll = ll
                    best_bgf = bgf
        except Exception:
            continue

    if best_bgf is None:
        cust = _fallback_clv(df, amount_col)
        top = cust.nlargest(20, "clv_predicted")
        return {
            "method": "heuristic_weighted",
            "clv_summary": {"mean": round(float(cust["clv_predicted"].mean()), 2)},
            "top_customers": top[["customer_id", "clv_predicted"]].to_dict("records"),
            "total_customers": len(cust),
        }

    summary["predicted_purchases"] = best_bgf.conditional_expected_number_of_purchases_up_to_time(
        90, summary["frequency"], summary["recency"], summary["T"]
    )

    # Gamma-Gamma for monetary
    ggf = GammaGammaFitter(penalizer_coef=0.01)
    ggf.fit(summary["frequency"], summary["monetary_value"])

    summary["clv_predicted"] = ggf.customer_lifetime_value(
        best_bgf,
        summary["frequency"],
        summary["recency"],
        summary["T"],
        summary["monetary_value"],
        time=12,
        discount_rate=0.01,
    ).round(2)

    # Update DB
    for cid, row in summary.iterrows():
        session.execute(
            text("UPDATE customers SET clv_predicted = :clv, updated_at = NOW() WHERE external_id = :cid"),
            {"clv": float(row["clv_predicted"]), "cid": str(cid)},
        )
    session.commit()

    top = summary.nlargest(20, "clv_predicted").reset_index()
    top_records = top[
        ["customer_id", "clv_predicted", "frequency", "monetary_value", "predicted_purchases"]
    ].to_dict("records")

    return {
        "method": "bg_nbd_gamma_gamma",
        "clv_summary": {
            "mean": round(float(summary["clv_predicted"].mean()), 2),
            "median": round(float(summary["clv_predicted"].median()), 2),
            "p75": round(float(summary["clv_predicted"].quantile(0.75)), 2),
            "p90": round(float(summary["clv_predicted"].quantile(0.90)), 2),
            "total": round(float(summary["clv_predicted"].sum()), 2),
        },
        "top_customers": top_records,
        "total_customers": len(summary),
    }
