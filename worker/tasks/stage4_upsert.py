"""Stage 4 — Upsert dimensions + dispatch analytics chord.

Two responsibilities:

1.  **Dimension upserts** (customers, products, orders) — populate the
    relational tables the frontend reads for the customer/product list
    pages. Order rows are linked back to internal Customer.id via a
    DataFrame merge (no `iterrows`).

2.  **Module dispatch** — for every module whose required columns are
    present AND whose `fn` is registered, fire `tasks.analytics.run_module`
    in a chord. The chord callback is `stage6_finalize`. Modules that are
    eligible by columns but have no `fn` yet are marked "skipped" with
    reason "not_implemented" so the UI shows a clear "Coming soon" state.

Performance notes:
- All three dimension upserts use vectorized pandas → list-of-dicts then a
  single `INSERT … ON CONFLICT` per table. No per-row Python loops.
- Order rows whose customer hasn't been inserted are filtered via a
  DataFrame merge (NaN → drop) instead of a per-row `dict.get`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pandas as pd
from celery import shared_task, chord, signature
from sqlalchemy.dialects.postgresql import insert

from sqlalchemy import text

from db import get_db_session
from app.models.upload_job import UploadJob
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order
from app.models.analytics_module_status import AnalyticsModuleStatus

import schema

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
CLEANED_DIR = os.path.join(UPLOAD_DIR, "cleaned")


# ── Helpers ─────────────────────────────────────────────────────────────────


def _vectorize_str(df: pd.DataFrame, col: str, default: Any = None) -> pd.Series:
    """Return df[col].astype(str) if present, else a Series of `default`."""
    if col in df.columns:
        s = df[col]
        # Replace pandas NA / NaN with the provided default before casting.
        return s.where(s.notna(), default)
    return pd.Series([default] * len(df), index=df.index)


def _build_customer_records(df: pd.DataFrame, user_id) -> List[Dict[str, Any]]:
    """Vectorized one-row-per-customer record list. Latest row per customer wins."""
    if "customer_id" not in df.columns:
        return []
    sort_col = "order_date" if "order_date" in df.columns else None
    cust_df = (
        df.sort_values(sort_col) if sort_col else df
    ).drop_duplicates("customer_id", keep="last").copy()

    cust_df["customer_id"] = cust_df["customer_id"].astype(str)
    out = pd.DataFrame(index=cust_df.index)
    out["user_id"] = user_id
    out["external_id"] = cust_df["customer_id"]
    # Default email so the NOT NULL email column is always satisfied.
    fallback_email = cust_df["customer_id"] + "@placeholder.insightx"
    out["email"] = _vectorize_str(cust_df, "customer_email", None).fillna(fallback_email)
    out["full_name"] = _vectorize_str(cust_df, "customer_name", None)
    out["country"] = _vectorize_str(cust_df, "country", None)
    out["country_code"] = _vectorize_str(cust_df, "country_code", None)
    out["region"] = _vectorize_str(cust_df, "region", None)
    out["gender"] = _vectorize_str(cust_df, "gender", None)
    # first_purchase_date: prefer registration_date, fall back to order_date.
    first_pd = None
    if "registration_date" in cust_df.columns:
        first_pd = cust_df["registration_date"]
    elif "order_date" in cust_df.columns:
        first_pd = cust_df["order_date"]
    out["first_purchase_date"] = first_pd if first_pd is not None else pd.NaT
    # age_group: keep as string ("under-18", "25-34") if present, else None.
    out["age_group"] = _vectorize_str(cust_df, "age", None)
    out["is_active"] = True

    # Convert pandas NaT/NaN -> None for SQLAlchemy.
    return out.where(out.notna(), None).to_dict("records")


def _build_product_records(df: pd.DataFrame, user_id) -> List[Dict[str, Any]]:
    if "product_id" not in df.columns:
        return []
    sort_col = "order_date" if "order_date" in df.columns else None
    prod_df = (
        df.sort_values(sort_col) if sort_col else df
    ).drop_duplicates("product_id", keep="last").copy()
    # Product.sku is VARCHAR(20) — truncate aggressively. Long product_ids
    # (UUIDs etc.) crash the insert otherwise.
    prod_df["product_id"] = prod_df["product_id"].astype(str).str[:20]

    out = pd.DataFrame(index=prod_df.index)
    out["user_id"] = user_id
    out["sku"] = prod_df["product_id"]
    fallback_name = "Product " + prod_df["product_id"]
    out["name"] = _vectorize_str(prod_df, "product_name", None).fillna(fallback_name).astype(str).str[:500]
    out["category"] = _vectorize_str(prod_df, "category", "Uncategorized").astype(str).str[:100]
    out["description"] = _vectorize_str(prod_df, "product_description", None)
    # If no unit_price, fall back to total_amount as a rough proxy.
    if "unit_price" in prod_df.columns:
        out["unit_price"] = prod_df["unit_price"]
    elif "total_amount" in prod_df.columns:
        out["unit_price"] = prod_df["total_amount"]
    else:
        out["unit_price"] = 0
    out["cost_price"] = prod_df["cost_amount"] if "cost_amount" in prod_df.columns else None
    out["supplier"] = _vectorize_str(prod_df, "supplier", None).astype(str).str[:100] if "supplier" in prod_df.columns else None
    out["stock_qty"] = prod_df["stock_qty"] if "stock_qty" in prod_df.columns else 0
    out["is_active"] = True

    return out.where(out.notna(), None).to_dict("records")


def _build_order_records(df: pd.DataFrame, user_id, cust_id_map: dict,
                         job_id) -> List[Dict[str, Any]]:
    """Per-order rows linked to internal Customer.id via vectorized merge.

    Honors the Order table's NOT NULL constraints:
      - order_date, total_amount, net_amount, discount_amount, region,
        currency, status, return_flag

    For columns absent from the CSV we provide safe defaults so the insert
    doesn't fail downstream. `net_amount` defaults to `total_amount`,
    `discount_amount` to 0, `region` to "Unknown".
    """
    if "order_id" not in df.columns:
        # Synthesize order_ids deterministically so re-upload is idempotent.
        df = df.assign(order_id=[f"AUTO-{job_id}-{i}" for i in range(len(df))])

    orders_df = df.drop_duplicates("order_id").copy()
    orders_df["customer_id"] = orders_df["customer_id"].astype(str) if "customer_id" in orders_df.columns else None
    # Map external_id → internal Customer.id. Drop rows we can't resolve.
    if "customer_id" in orders_df.columns:
        orders_df["_internal_cid"] = orders_df["customer_id"].map(cust_id_map)
        orders_df = orders_df.dropna(subset=["_internal_cid"])
    else:
        orders_df["_internal_cid"] = None

    # Order needs a non-null order_date — drop rows we can't satisfy.
    if "order_date" in orders_df.columns:
        orders_df = orders_df.dropna(subset=["order_date"])

    if orders_df.empty:
        return []

    out = pd.DataFrame(index=orders_df.index)
    out["user_id"] = user_id
    out["upload_job_id"] = job_id
    out["customer_id"] = orders_df["_internal_cid"]
    # Column is `external_id` in the Order ORM (and DB) — NOT `order_number`.
    # VARCHAR(50) so truncate defensively.
    out["external_id"] = orders_df["order_id"].astype(str).str[:50]
    out["order_date"] = orders_df["order_date"]

    # NOT NULL numerics — fall back from CSV → total_amount → 0.
    total = orders_df["total_amount"] if "total_amount" in orders_df.columns else 0
    out["total_amount"] = total
    if "net_amount" in orders_df.columns:
        out["net_amount"] = orders_df["net_amount"].fillna(total) if hasattr(orders_df["net_amount"], "fillna") else total
    else:
        out["net_amount"] = total
    if "discount_amount" in orders_df.columns:
        out["discount_amount"] = orders_df["discount_amount"].fillna(0) if hasattr(orders_df["discount_amount"], "fillna") else 0
    else:
        out["discount_amount"] = 0

    # NOT NULL strings.
    out["region"] = _vectorize_str(orders_df, "region", "Unknown").astype(str).str[:50]
    out["currency"] = _vectorize_str(orders_df, "currency", "USD").astype(str).str[:3]
    out["status"] = _vectorize_str(orders_df, "status", "completed").astype(str).str[:30]

    # Nullable extras (truncate to varchar bounds).
    out["acquisition_channel"] = _vectorize_str(orders_df, "acquisition_channel", None)
    if hasattr(out["acquisition_channel"], "astype"):
        out["acquisition_channel"] = out["acquisition_channel"].astype("object").where(
            out["acquisition_channel"].notna(), None
        )
    out["payment_method"] = _vectorize_str(orders_df, "payment_method", None)
    out["return_flag"] = orders_df["return_flag"] if "return_flag" in orders_df.columns else False
    out["delivery_days"] = orders_df["delivery_days"] if "delivery_days" in orders_df.columns else None
    out["comment_text"] = _vectorize_str(orders_df, "comment_text", None)
    out["cost_amount"] = orders_df["cost_amount"] if "cost_amount" in orders_df.columns else None

    return out.where(out.notna(), None).to_dict("records")


# ── Main task ───────────────────────────────────────────────────────────────


_BATCH_SIZE = 500   # Max records per INSERT to stay within PostgreSQL's 65k bind-param limit


def _batch_insert(db, stmt_factory, records: list, batch_size: int = _BATCH_SIZE) -> None:
    """Execute an INSERT statement in chunks to avoid exceeding bind-param limits."""
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        db.execute(stmt_factory(batch))
    db.commit()


@shared_task(name="tasks.pipeline.stage4_upsert", bind=True)
def stage4_upsert(self, job_id_str: str) -> str:
    db = get_db_session()
    try:
        job = db.query(UploadJob).filter(UploadJob.id == job_id_str).first()
    except Exception:
        db.close()
        raise

    try:
        return _stage4_inner(db, job, job_id_str)
    except Exception as exc:
        # Surface the error as a terminal job status so pollers don't time-out.
        try:
            job.status = "failed"
            job.error_message = str(exc)[:500]
            db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


def _stage4_inner(db, job, job_id_str: str) -> str:
    """Core stage-4 logic extracted so the task wrapper can catch all errors."""
    if not job:
        raise ValueError(f"Job {job_id_str} not found")

    parquet_path = os.path.join(CLEANED_DIR, f"{job_id_str}.parquet")
    df = pd.read_parquet(parquet_path)
    available_columns = set(df.columns)
    user_id = job.user_id

    # ── 0. CLEAN SLATE ──
    # Each new upload IS the user's current dataset. Old customers /
    # products / orders are wiped so every dashboard page reflects only
    # this CSV. Orders cascade-delete via the customers FK (ON DELETE
    # CASCADE). Upload history (upload_jobs, analytics_module_status,
    # analysis_results_cache) is kept — the readers naturally pick the
    # latest job's results.
    db.execute(
        text("DELETE FROM customers WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    db.execute(
        text("DELETE FROM products  WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    db.commit()

    # ── 1. CUSTOMERS ──
    # Customer has TWO unique constraints — (user_id, external_id) AND
    # (user_id, email). Plain `on_conflict_do_update(index_elements=...)`
    # can only target ONE, so a CSV with duplicate emails (or a re-upload
    # against existing email rows) crashes the second constraint. Using
    # `on_conflict_do_nothing()` with no target catches ANY UQ violation
    # and silently skips that row. Trade-off: existing customer details
    # don't refresh across re-uploads — but the pipeline doesn't crash,
    # which is the priority right now.
    cust_records = _build_customer_records(df, user_id)
    if cust_records:
        # Pre-dedupe the batch by email to avoid intra-batch conflict
        seen_emails = set()
        seen_extids = set()
        unique_records = []
        for r in cust_records:
            email = r.get("email")
            extid = r.get("external_id")
            if email in seen_emails or extid in seen_extids:
                continue
            seen_emails.add(email)
            seen_extids.add(extid)
            unique_records.append(r)
        # Use batched inserts to stay within PostgreSQL's 65k bind-param limit
        _batch_insert(
            db,
            lambda batch: insert(Customer).values(batch).on_conflict_do_nothing(),
            unique_records,
        )

    # ── 2. PRODUCTS ──
    # Same defensive treatment as customers — Product has (user_id, sku).
    # If future schemas add more UQs, this still won't crash.
    prod_records = _build_product_records(df, user_id)
    if prod_records:
        seen_skus = set()
        unique_records = []
        for r in prod_records:
            sku = r.get("sku")
            if sku in seen_skus:
                continue
            seen_skus.add(sku)
            unique_records.append(r)
        _batch_insert(
            db,
            lambda batch: insert(Product).values(batch).on_conflict_do_nothing(),
            unique_records,
        )

    # ── 3. ORDERS ──
    cust_id_map = dict(
        db.query(Customer.external_id, Customer.id)
          .filter(Customer.user_id == user_id).all()
    )
    order_records = _build_order_records(df, user_id, cust_id_map, job.id)
    if order_records:
        def _order_stmt(batch):
            return (insert(Order).values(batch)
                    .on_conflict_do_nothing(index_elements=["user_id", "external_id"]))
        _batch_insert(db, _order_stmt, order_records)
        db.commit()

    # ── 3.5 DENORMALIZE CUSTOMER STATS ──
    # The customers list page reads total_orders, lifetime_value, etc.
    # directly from the customers table. The analytics modules write to
    # analysis_results_cache only, so without this step those fields stay
    # at 0. We aggregate from the just-inserted orders.
    db.execute(text("""
        UPDATE customers c SET
            total_orders        = sub.cnt,
            lifetime_value      = sub.rev,
            first_purchase_date = COALESCE(c.first_purchase_date, sub.first_order::date),
            last_active_at      = sub.last_order
          FROM (
            SELECT customer_id,
                   COUNT(*)                                    AS cnt,
                   COALESCE(SUM(net_amount), 0)                AS rev,
                   MIN(order_date)                             AS first_order,
                   MAX(order_date)::timestamptz                AS last_order
              FROM orders
             WHERE user_id = :uid
             GROUP BY customer_id
          ) sub
         WHERE c.id = sub.customer_id AND c.user_id = :uid
    """), {"uid": user_id})
    db.commit()

    # ── 3.6 DENORMALIZE PRODUCT STATS ──
    # Aggregate from the parquet (we don't insert order_items, so SQL
    # alone can't link orders→products). Skip if no product_id column.
    if "product_id" in df.columns and "total_amount" in df.columns:
        prod_df = df.copy()
        prod_df["product_id"] = prod_df["product_id"].astype(str).str[:20]
        agg_dict = {
            "total_revenue": ("total_amount", "sum"),
            "total_units_sold": (
                "quantity" if "quantity" in prod_df.columns else "total_amount",
                "sum" if "quantity" in prod_df.columns else "count",
            ),
        }
        prod_stats = prod_df.groupby("product_id").agg(**agg_dict).reset_index()

        updates = [
            {
                "sku": str(r.product_id),
                "rev": float(r.total_revenue or 0),
                "units": int(r.total_units_sold or 0),
                "uid": str(user_id),
            }
            for r in prod_stats.itertuples()
        ]
        if updates:
            db.execute(
                text("""
                    UPDATE products SET
                        total_revenue    = :rev,
                        total_units_sold = :units
                      WHERE sku = :sku AND user_id = CAST(:uid AS uuid)
                """),
                updates,
            )
            db.commit()

    # ── 4. MODULE ELIGIBILITY + STATUS ROWS ──
    # Clear any prior status rows from re-uploads.
    db.query(AnalyticsModuleStatus).filter(
        AnalyticsModuleStatus.upload_job_id == job_id_str
    ).delete()

    eligibility = schema.check_eligibility(available_columns)
    status_records = []
    eligible_keys: List[str] = []

    for key, res in eligibility.items():
        mod = res["module"]
        cols_ok = bool(res["can_run"])
        fn_ready = mod.fn is not None

        # Determine status + dispatch decision
        if not cols_ok:
            run_status, error_msg = "skipped", None
        elif not fn_ready:
            run_status = "skipped"
            error_msg = "not implemented yet"
        else:
            run_status, error_msg = "pending", None
            eligible_keys.append(key)

        status_records.append(AnalyticsModuleStatus(
            upload_job_id=job.id,
            module_key=mod.key,
            module_name=mod.name,
            module_name_ar=mod.name_ar,
            description=mod.description,
            queue=mod.queue,
            can_run=cols_ok and fn_ready,
            missing_required_columns=res["missing_required"],
            missing_optional_columns=res["missing_optional"],
            run_status=run_status,
            error_message=error_msg,
        ))

    db.add_all(status_records)
    job.status = "analyzing"
    db.commit()

    # ── 5. FIRE CHORD ──
    # One stage5_run_module signature per eligible key. Callback is
    # stage6_finalize, which Celery auto-feeds the chord results list.
    if eligible_keys:
        header = [
            signature("tasks.analytics.run_module", args=[job_id_str, key])
            for key in eligible_keys
        ]
        callback = signature("tasks.pipeline.stage6_finalize", args=[job_id_str])
        chord(header)(callback)
    else:
        # No eligible modules — skip straight to finalize.
        signature("tasks.pipeline.stage6_finalize", args=[[], job_id_str]).delay()

    return f"Dispatched {len(eligible_keys)} of {len(eligibility)} modules"
