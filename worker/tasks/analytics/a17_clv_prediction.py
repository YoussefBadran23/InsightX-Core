"""A17 — CLV Prediction (Optimized & Complete)."""
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

# RAM Optimization
COLS = ["customer_id", "created_at", "total_amount", "net_amount"]

def _fallback_clv(df, amount_col):
    """Weighted heuristic using frequency and recency decay."""
    ref_date = df["created_at"].max() + pd.Timedelta(days=1)
    cust = df.groupby("customer_id").agg(
        total_spend=(amount_col, "sum"),
        n_orders=(amount_col, "count"),
        first=("created_at", "min"),
        last=("created_at", "max")
    ).reset_index()
    cust["tenure"] = (ref_date - cust["first"]).dt.days.clip(lower=1)
    cust["recency"] = (ref_date - cust["last"]).dt.days
    # CLV = annualized revenue * recency decay
    cust["clv_predicted"] = (cust["total_spend"] / cust["tenure"] * 365 * np.exp(-0.693 * cust["recency"] / 90)).round(2)
    return cust

@analytics_task("A17_clv_prediction", "clv", required_cols=COLS)
def run_clv_prediction(df, session, job_id):
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    amt = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", "created_at", amt])
    df = df[df[amt] > 0]

    if len(df) < 10: return {"summary": "Insufficient data"}

    if _HAS_LIFETIMES:
        summary = summary_data_from_transaction_data(df, "customer_id", "created_at", amt)
        summary = summary[summary["frequency"] > 0]
        if len(summary) > 10:
            try:
                bgf = BetaGeoFitter(penalizer_coef=0.01).fit(summary["frequency"], summary["recency"], summary["T"])
                ggf = GammaGammaFitter(penalizer_coef=0.01).fit(summary["frequency"], summary["monetary_value"])
                summary["clv_predicted"] = ggf.customer_lifetime_value(bgf, summary["frequency"], summary["recency"], 
                                                                      summary["T"], summary["monetary_value"], time=12)
                results = summary[["clv_predicted"]].reset_index()
                method = "bg_nbd_gamma_gamma"
            except:
                results, method = _fallback_clv(df, amt), "heuristic_fallback"
        else:
            results, method = _fallback_clv(df, amt), "heuristic_fallback"
    else:
        results, method = _fallback_clv(df, amt), "heuristic_weighted"

    # PERFORMANCE WIN: Batch Update
    batch = [{"clv": float(r.clv_predicted), "cid": str(r.customer_id if hasattr(r, 'customer_id') else r.Index)} for r in results.itertuples()]
    if batch:
        session.execute(text("UPDATE customers SET clv_predicted = :clv, updated_at = NOW() WHERE external_id = :cid"), batch)
        session.commit()

    return {
        "method": method,
        "clv_summary": {
            "mean": round(float(results["clv_predicted"].mean()), 2),
            "total": round(float(results["clv_predicted"].sum()), 2)
        },
        "top_customers": results.nlargest(20, "clv_predicted").to_dict("records")
    }