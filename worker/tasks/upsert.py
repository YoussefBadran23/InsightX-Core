"""Phase 3 — Step 10: Auto-Pipeline Stage 4 & 5 — Entity & Dimension Upserts.

Reads the cleaned Parquet from Stage 3, upserts customers and products,
bulk-inserts orders and order_items, and recalculates denormalized counters.

Flow:
  preprocess.py (Stage 3: validation)
    → upsert.py (Stage 4-5: entity & dimension inserts)  ← THIS FILE
      → analytics chord (Stage 6: 22 parallel modules)
"""

import os
import uuid
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from celery import chord, signature
from celery_app import celery_app
from app.models.upload_job import UploadJob
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order
from app.models.order_item import OrderItem

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

CLEANED_DIR = "/app/uploads/cleaned"

# Batch size for bulk inserts to avoid OOM on large files
_BATCH_SIZE = int(os.getenv("UPSERT_BATCH_SIZE", "1000"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_str(val, default="") -> str:
    """Convert value to string, replacing NaN/None with default."""
    if pd.isna(val):
        return default
    return str(val).strip()


def _safe_decimal(val, default=Decimal("0.00")) -> Decimal:
    if pd.isna(val):
        return default
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"))
    except Exception:
        return default


def _safe_int(val, default=0) -> int:
    if pd.isna(val):
        return default
    try:
        return int(float(val))
    except Exception:
        return default


def _safe_date(val) -> date | None:
    if pd.isna(val):
        return None
    try:
        return pd.Timestamp(val).date()
    except Exception:
        return None


def _safe_bool(val, default=False) -> bool:
    if pd.isna(val):
        return default
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes", "t", "y")


# ── Main task ─────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.upsert.run_upserts")
def run_upserts(self, job_id: str):
    """
    Stage 4-5: Read cleaned Parquet, upsert entities, insert facts.

    1. Load cleaned Parquet from Stage 3.
    2. Upsert unique customers (by external_id or email).
    3. Upsert unique products (by SKU or product_id).
    4. Bulk-insert orders with FK references.
    5. Bulk-insert order_items with FK references.
    6. Recalculate denormalized counters on customers and products.
    7. Update job status → "insert_complete".
    """
    logger.info("Starting entity upserts for job %s", job_id)
    db = SessionLocal()

    try:
        job = db.query(UploadJob).filter(UploadJob.id == job_id).first()
        if not job:
            logger.error("Job %s not found.", job_id)
            return {"status": "error", "message": "Job not found"}

        job.status = "inserting"
        db.commit()

        # ── 1. Load cleaned Parquet ──────────────────────────────────────
        parquet_path = os.path.join(CLEANED_DIR, f"{job_id}_cleaned.parquet")
        if not os.path.exists(parquet_path):
            job.status = "failed"
            job.error_message = "Cleaned Parquet file not found."
            db.commit()
            return {"status": "failed", "message": "Parquet not found"}

        df = pd.read_parquet(parquet_path, engine="pyarrow")
        logger.info("Job %s: loaded %d cleaned rows from Parquet.", job_id, len(df))

        if len(df) == 0:
            job.status = "failed"
            job.error_message = "No valid rows to insert."
            db.commit()
            return {"status": "failed", "message": "Empty dataset"}

        # ── 2. Upsert Customers ──────────────────────────────────────────
        customer_id_map: dict[str, uuid.UUID] = {}  # external_id → DB UUID

        if "customer_id" in df.columns:
            unique_customers = df.drop_duplicates(subset=["customer_id"])
            logger.info("Job %s: upserting %d unique customers.", job_id, len(unique_customers))

            for _, row in unique_customers.iterrows():
                ext_id = _safe_str(row.get("customer_id"))
                if not ext_id:
                    continue

                # Try to find existing customer by external_id
                existing = (
                    db.query(Customer)
                    .filter(Customer.external_id == ext_id)
                    .first()
                )

                if existing:
                    # Update fields if new data is richer
                    if "full_name" in df.columns and not pd.isna(row.get("full_name")):
                        existing.full_name = _safe_str(row.get("full_name"))
                    if "country" in df.columns and not pd.isna(row.get("country")):
                        existing.country = _safe_str(row.get("country"))
                    if "country_code" in df.columns and not pd.isna(row.get("country_code")):
                        existing.country_code = _safe_str(row.get("country_code"))
                    if "region" in df.columns and not pd.isna(row.get("region")):
                        existing.region = _safe_str(row.get("region"))
                    customer_id_map[ext_id] = existing.id
                else:
                    # Generate an email if not provided
                    email = _safe_str(row.get("email"))
                    if not email:
                        email = f"{ext_id}@imported.insightx.local"

                    new_customer = Customer(
                        external_id=ext_id,
                        email=email,
                        full_name=_safe_str(row.get("full_name"), default=ext_id),
                        country=_safe_str(row.get("country")) or None,
                        country_code=_safe_str(row.get("country_code")) or None,
                        region=_safe_str(row.get("region")) or "NA",
                        is_active=True,
                    )
                    db.add(new_customer)
                    db.flush()
                    customer_id_map[ext_id] = new_customer.id

            db.commit()
            logger.info("Job %s: customers upserted. %d in map.", job_id, len(customer_id_map))

        # ── 3. Upsert Products ───────────────────────────────────────────
        product_id_map: dict[str, uuid.UUID] = {}  # sku/product_id → DB UUID

        if "product_id" in df.columns:
            unique_products = df.drop_duplicates(subset=["product_id"])
            logger.info("Job %s: upserting %d unique products.", job_id, len(unique_products))

            for _, row in unique_products.iterrows():
                sku = _safe_str(row.get("product_id"))
                if not sku:
                    continue

                # Truncate SKU to 20 chars to fit schema
                sku = sku[:20]

                existing = db.query(Product).filter(Product.sku == sku).first()

                if existing:
                    # Update price if provided
                    if "unit_price" in df.columns and not pd.isna(row.get("unit_price")):
                        existing.unit_price = _safe_decimal(row.get("unit_price"))
                    if "cost_price" in df.columns and not pd.isna(row.get("cost_price")):
                        existing.cost_price = _safe_decimal(row.get("cost_price"))
                    if "category" in df.columns and not pd.isna(row.get("category")):
                        existing.category = _safe_str(row.get("category"))
                    product_id_map[sku] = existing.id
                else:
                    new_product = Product(
                        sku=sku,
                        name=_safe_str(row.get("name"), default=sku),
                        category=_safe_str(row.get("category"), default="Uncategorized"),
                        unit_price=_safe_decimal(row.get("unit_price")),
                        cost_price=_safe_decimal(row.get("cost_price")) if "cost_price" in df.columns and not pd.isna(row.get("cost_price")) else None,
                        is_active=True,
                    )
                    db.add(new_product)
                    db.flush()
                    product_id_map[sku] = new_product.id

            db.commit()
            logger.info("Job %s: products upserted. %d in map.", job_id, len(product_id_map))

        # ── 4. Bulk-insert Orders ────────────────────────────────────────
        # Group by order external_id to avoid duplicate orders
        has_order_id = "id" in df.columns  # mapped from "order_id" → "id"
        order_id_map: dict[str, uuid.UUID] = {}  # external_order_id → DB UUID

        if has_order_id:
            unique_orders = df.drop_duplicates(subset=["id"])
        else:
            # No order ID column — every row is treated as a separate order
            unique_orders = df.copy()
            unique_orders["id"] = [f"auto_{i}" for i in range(len(unique_orders))]

        logger.info("Job %s: inserting %d orders.", job_id, len(unique_orders))
        orders_inserted = 0

        for batch_start in range(0, len(unique_orders), _BATCH_SIZE):
            batch = unique_orders.iloc[batch_start:batch_start + _BATCH_SIZE]

            for _, row in batch.iterrows():
                ext_order_id = _safe_str(row.get("id"))

                # Skip if order already exists
                if ext_order_id and not ext_order_id.startswith("auto_"):
                    existing_order = (
                        db.query(Order)
                        .filter(Order.external_id == ext_order_id)
                        .first()
                    )
                    if existing_order:
                        order_id_map[ext_order_id] = existing_order.id
                        continue

                # Resolve customer FK
                ext_cust = _safe_str(row.get("customer_id"))
                db_customer_id = customer_id_map.get(ext_cust)
                if not db_customer_id:
                    # Create a fallback unknown customer
                    fallback_ext = ext_cust or f"unknown_{uuid.uuid4().hex[:8]}"
                    fallback = Customer(
                        external_id=fallback_ext,
                        email=f"{fallback_ext}@unknown.insightx.local",
                        full_name="Unknown Customer",
                        region="NA",
                        is_active=True,
                    )
                    db.add(fallback)
                    db.flush()
                    customer_id_map[fallback_ext] = fallback.id
                    db_customer_id = fallback.id

                total = _safe_decimal(row.get("total_amount"))
                discount = _safe_decimal(row.get("discount_amount"))
                net = total - discount
                cost = _safe_decimal(row.get("cost_amount")) if "cost_amount" in df.columns and not pd.isna(row.get("cost_amount")) else None
                gross_margin = (net - cost) if cost is not None else None

                order = Order(
                    external_id=ext_order_id if ext_order_id and not ext_order_id.startswith("auto_") else None,
                    customer_id=db_customer_id,
                    upload_job_id=job.id,
                    order_date=_safe_date(row.get("created_at")) or date.today(),
                    total_amount=total,
                    discount_amount=discount,
                    net_amount=net,
                    cost_amount=cost,
                    gross_margin=gross_margin,
                    region=_safe_str(row.get("region"), default="NA"),
                    currency=_safe_str(row.get("currency"), default="USD"),
                    status=_safe_str(row.get("status"), default="completed"),
                    payment_method=_safe_str(row.get("payment_method")) or None,
                    acquisition_channel=_safe_str(row.get("acquisition_channel")) or None,
                    return_flag=_safe_bool(row.get("return_flag")),
                    delivery_days=_safe_int(row.get("delivery_days")) if "delivery_days" in df.columns and not pd.isna(row.get("delivery_days")) else None,
                    comment_text=_safe_str(row.get("comment_text")) or None,
                )
                db.add(order)
                db.flush()
                order_id_map[ext_order_id] = order.id
                orders_inserted += 1

            db.commit()
            # Update progress
            job.rows_processed = orders_inserted
            db.commit()

        logger.info("Job %s: inserted %d orders.", job_id, orders_inserted)

        # ── 5. Bulk-insert Order Items ───────────────────────────────────
        items_inserted = 0

        if "product_id" in df.columns:
            logger.info("Job %s: inserting order items.", job_id)

            for batch_start in range(0, len(df), _BATCH_SIZE):
                batch = df.iloc[batch_start:batch_start + _BATCH_SIZE]

                for _, row in batch.iterrows():
                    ext_order_id = _safe_str(row.get("id"))
                    if has_order_id and ext_order_id:
                        db_order_id = order_id_map.get(ext_order_id)
                    else:
                        # For auto-generated IDs, match by row position
                        auto_key = f"auto_{row.name}" if not has_order_id else ext_order_id
                        db_order_id = order_id_map.get(auto_key)

                    sku = _safe_str(row.get("product_id"))[:20]
                    db_product_id = product_id_map.get(sku)

                    if not db_order_id or not db_product_id:
                        continue

                    qty = max(_safe_int(row.get("quantity"), default=1), 1)
                    unit_price = _safe_decimal(row.get("unit_price"))
                    line_total = Decimal(str(qty)) * unit_price

                    item = OrderItem(
                        order_id=db_order_id,
                        product_id=db_product_id,
                        quantity=qty,
                        unit_price=unit_price,
                        line_total=line_total,
                    )
                    db.add(item)
                    items_inserted += 1

                db.commit()

            logger.info("Job %s: inserted %d order items.", job_id, items_inserted)

        # ── 6. Recalculate denormalized counters ─────────────────────────
        logger.info("Job %s: recalculating denormalized counters.", job_id)

        # Customer counters: total_orders, lifetime_value, first_purchase_date, last_active_at, cohort_month
        db.execute(text("""
            UPDATE customers c SET
                total_orders = sub.cnt,
                lifetime_value = sub.ltv,
                first_purchase_date = sub.first_date,
                last_active_at = sub.last_date,
                cohort_month = DATE_TRUNC('month', sub.first_date)
            FROM (
                SELECT
                    customer_id,
                    COUNT(*) AS cnt,
                    COALESCE(SUM(net_amount), 0) AS ltv,
                    MIN(order_date) AS first_date,
                    MAX(order_date)::timestamptz AS last_date
                FROM orders
                WHERE upload_job_id = :job_id
                GROUP BY customer_id
            ) sub
            WHERE c.id = sub.customer_id
        """), {"job_id": job_id})

        # Product counters: total_revenue, total_units_sold
        db.execute(text("""
            UPDATE products p SET
                total_revenue = sub.rev,
                total_units_sold = sub.units
            FROM (
                SELECT
                    oi.product_id,
                    COALESCE(SUM(oi.line_total), 0) AS rev,
                    COALESCE(SUM(oi.quantity), 0) AS units
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE o.upload_job_id = :job_id
                GROUP BY oi.product_id
            ) sub
            WHERE p.id = sub.product_id
        """), {"job_id": job_id})

        db.commit()
        logger.info("Job %s: denormalized counters updated.", job_id)

        # ── 7. Update job status ─────────────────────────────────────────
        job.rows_processed = orders_inserted
        job.status = "analyzing"
        db.commit()

        logger.info(
            "Job %s: Stage 4-5 (upserts) complete — %d orders, %d items.",
            job_id, orders_inserted, items_inserted,
        )

        # ── 8. Dispatch eligible analytics modules ─────────────────────────
        # Only dispatch modules that have a registered Celery task to avoid
        # "task not found" errors for unimplemented modules (A15-A22).
        _IMPLEMENTED_MODULES = {
            "A01_revenue_summary", "A02_rfm_scoring", "A03_market_basket",
            "A04_gross_margin", "A05_cohort_retention", "A06_geographic_revenue",
            "A07_abc_classification", "A08_aov_trends", "A09_top_n_products",
            "A10_customer_lifetime", "A11_order_status", "A12_discount_impact",
            "A13_growth_rates", "A14_acquisition_channel",
            "A15_prophet_forecast", "A16_anomaly_detection", "A17_clv_prediction",
            "A18_sentiment_analysis", "A19_customer_segmentation", "A20_churn_prediction",
            "A21_return_rate", "A22_fulfillment_sla",
        }

        eligible = db.execute(
            text("""
                SELECT module_key FROM analytics_module_status
                WHERE upload_job_id = :job_id
                  AND can_run = TRUE
            """),
            {"job_id": job_id},
        ).fetchall()

        dispatched = 0
        skipped = 0
        task_signatures = []

        for (module_key,) in eligible:
            if module_key not in _IMPLEMENTED_MODULES:
                logger.warning(
                    "Job %s: skipping module %s — not yet implemented.",
                    job_id, module_key,
                )
                db.execute(
                    text("""
                        UPDATE analytics_module_status
                        SET run_status = 'skipped',
                            error_message = 'Module not yet implemented'
                        WHERE upload_job_id = :job_id AND module_key = :key
                    """),
                    {"job_id": job_id, "key": module_key},
                )
                skipped += 1
                continue

            task_signatures.append(
                signature(
                    f"tasks.analytics.{module_key}",
                    args=[job_id],
                    queue="analytics",
                )
            )
            dispatched += 1

        if skipped:
            db.commit()

        # Wire chord: run all analytics in parallel → finalize callback
        if task_signatures:
            callback = signature(
                "tasks.finalize.run_finalize",
                kwargs={"job_id": job_id},
            )
            chord(task_signatures)(callback)
            logger.info(
                "Job %s: chord dispatched — %d analytics tasks → finalize callback, %d skipped.",
                job_id, dispatched, skipped,
            )
        else:
            # No analytics to run — finalize immediately
            celery_app.send_task("tasks.finalize.run_finalize", args=[[], job_id])
            logger.info("Job %s: no analytics tasks eligible — finalize dispatched directly.", job_id)

        return {
            "status": "success",
            "orders_inserted": orders_inserted,
            "items_inserted": items_inserted,
            "customers_upserted": len(customer_id_map),
            "products_upserted": len(product_id_map),
            "analytics_dispatched": dispatched,
        }

    except Exception as e:
        logger.error("Job %s: upsert failed — %s", job_id, e, exc_info=True)
        try:
            job.status = "failed"
            job.error_message = f"Upsert error: {e}"
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=15, max_retries=3)
    finally:
        db.close()
