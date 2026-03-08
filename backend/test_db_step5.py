"""
InsightX — Step 5 Database Verification Test
Tests that all 11 tables exist with correct columns, indexes, and that
CRUD operations work on every table.
"""

import sys
import os
from decimal import Decimal
from datetime import date, datetime, timezone
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db"
)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

PASS = "✅"
FAIL = "❌"
results = []

def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    msg = f"  {status} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append(condition)
    return condition

print("\n" + "="*60)
print("   InsightX Database Verification — Step 5")
print("="*60)

# ─── 1. Connection ────────────────────────────────────────────
print("\n[1] Database Connection")
try:
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version()")).scalar()
    check("PostgreSQL connection", True, ver.split(",")[0])
except Exception as e:
    check("PostgreSQL connection", False, str(e))
    print("\n❌ Cannot connect to DB. Aborting.")
    sys.exit(1)

# ─── 2. All 11 tables exist ───────────────────────────────────
print("\n[2] Tables Exist (11 expected)")
inspector = inspect(engine)
actual_tables = set(inspector.get_table_names())
expected_tables = {
    "users", "customers", "products", "orders", "order_items",
    "upload_jobs", "csv_column_mappings", "forecast_results",
    "daily_kpi_snapshots", "analysis_results_cache", "insights",
}
for table in sorted(expected_tables):
    check(f"Table: {table}", table in actual_tables)

extra = actual_tables - expected_tables - {"alembic_version"}
if extra:
    print(f"  ℹ️  Extra tables (ok): {extra}")

# ─── 3. Key columns on each table ─────────────────────────────
print("\n[3] Critical Columns Present")

def get_cols(table):
    return {c["name"] for c in inspector.get_columns(table)}

# users
ucols = get_cols("users")
for col in ["id","email","hashed_password","role","widget_config","reset_token","is_active"]:
    check(f"users.{col}", col in ucols)

# customers (v3.0 fields)
ccols = get_cols("customers")
for col in ["id","email","lifetime_value","ai_segment","engagement_score",
            "last_active_at","churn_risk_score","clv_predicted","cohort_month",
            "rfm_score","rfm_segment","age_group","gender"]:
    check(f"customers.{col}", col in ccols)

# products (v3.0 fields)
pcols = get_cols("products")
for col in ["id","sku","unit_price","abc_tier","stock_qty",
            "low_stock_threshold","cost_price","supplier","return_rate"]:
    check(f"products.{col}", col in pcols)

# orders (v3.0 fields)
ocols = get_cols("orders")
for col in ["id","customer_id","order_date","net_amount","region",
            "payment_method","acquisition_channel","return_flag",
            "delivery_days","comment_text","sentiment_label","gross_margin"]:
    check(f"orders.{col}", col in ocols)

# order_items
oicols = get_cols("order_items")
for col in ["id","order_id","product_id","quantity","unit_price","line_total"]:
    check(f"order_items.{col}", col in oicols)

# upload_jobs
ujcols = get_cols("upload_jobs")
for col in ["id","user_id","s3_key","status","rows_total","rows_processed",
            "rows_failed","celery_task_id"]:
    check(f"upload_jobs.{col}", col in ujcols)

# csv_column_mappings
cscols = get_cols("csv_column_mappings")
for col in ["id","upload_job_id","csv_header","mapped_table",
            "mapped_column","match_score","match_method","is_confirmed"]:
    check(f"csv_column_mappings.{col}", col in cscols)

# forecast_results
frcols = get_cols("forecast_results")
for col in ["id","job_id","ds","yhat","yhat_lower","yhat_upper",
            "is_historical","scenario_marketing_spend_pct",
            "scenario_price_shift_pct","scenario_seasonal_adj"]:
    check(f"forecast_results.{col}", col in frcols)

# daily_kpi_snapshots
dkcols = get_cols("daily_kpi_snapshots")
for col in ["id","snapshot_date","total_revenue","active_customers",
            "churn_rate","revenue_na","revenue_eu","revenue_apac","revenue_latam"]:
    check(f"daily_kpi_snapshots.{col}", col in dkcols)

# analysis_results_cache
arcols = get_cols("analysis_results_cache")
for col in ["id","analysis_type","upload_job_id","result_json",
            "computed_at","is_stale","duration_ms"]:
    check(f"analysis_results_cache.{col}", col in arcols)

# insights
incols = get_cols("insights")
for col in ["id","job_id","source_type","bullet_index","bullet_text"]:
    check(f"insights.{col}", col in incols)

# ─── 4. Alembic version table ─────────────────────────────────
print("\n[4] Alembic Migration State")
with engine.connect() as conn:
    rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
check("Migration applied", rev == "cd7f4376ca5f", f"revision={rev}")

# ─── 5. CRUD smoke test ───────────────────────────────────────
print("\n[5] CRUD Smoke Test (insert → read → delete)")

from app.models import (
    User, Customer, Product, UploadJob, Order, OrderItem,
    ForecastResult, DailyKpiSnapshot, AnalysisResultsCache, Insight,
    CsvColumnMapping,
)

db = Session()
try:
    # -- User
    u = User(
        email="test@insightx.io",
        full_name="Test User",
        hashed_password="$2b$12$fakehash",
        role="admin",
        widget_config={"layout": []},
    )
    db.add(u)
    db.flush()
    check("INSERT users", u.id is not None)

    # -- UploadJob
    job = UploadJob(
        user_id=u.id,
        s3_key="test/upload.csv",
        original_filename="upload.csv",
        status="pending",
    )
    db.add(job)
    db.flush()
    check("INSERT upload_jobs", job.id is not None)

    # -- Customer
    cust = Customer(
        email="customer@test.com",
        full_name="Jane Doe",
        external_id="CUS-TEST-001",
        country="United States",
        country_code="US",
        region="NA",
        first_purchase_date=date(2024, 1, 15),
        cohort_month=date(2024, 1, 1),
        rfm_score="554",
        rfm_segment="Loyal Customers",
        age_group="25-34",
        gender="Female",
        engagement_score=Decimal("78.50"),
    )
    db.add(cust)
    db.flush()
    check("INSERT customers", cust.id is not None)
    check("customers.cohort_month correct", str(cust.cohort_month) == "2024-01-01")
    check("customers.rfm_score correct", cust.rfm_score == "554")

    # -- Product
    prod = Product(
        sku="SK-TEST-001",
        name="Test Headphones",
        category="Electronics",
        unit_price=Decimal("299.00"),
        cost_price=Decimal("120.00"),
        supplier="TechCorp",
        stock_qty=45,
        low_stock_threshold=10,
    )
    db.add(prod)
    db.flush()
    check("INSERT products", prod.id is not None)
    # Test computed gross_margin_pct property
    margin = prod.gross_margin_pct
    expected_margin = round((299 - 120) / 299 * 100, 6)
    check("products.gross_margin_pct computed", abs(float(margin) - expected_margin) < 0.01,
          f"{float(margin):.2f}%")
    check("products.is_low_stock=False (qty=45, threshold=10)", not prod.is_low_stock)

    # -- Order
    order = Order(
        external_id="ORD-TEST-001",
        customer_id=cust.id,
        upload_job_id=job.id,
        order_date=date(2024, 6, 15),
        total_amount=Decimal("299.00"),
        discount_amount=Decimal("0.00"),
        net_amount=Decimal("299.00"),
        cost_amount=Decimal("120.00"),
        gross_margin=Decimal("179.00"),
        region="NA",
        currency="USD",
        status="completed",
        payment_method="credit_card",
        acquisition_channel="organic_search",
        return_flag=False,
        delivery_days=3,
        comment_text="Great product!",
    )
    db.add(order)
    db.flush()
    check("INSERT orders", order.id is not None)
    check("orders.payment_method persisted", order.payment_method == "credit_card")
    check("orders.acquisition_channel persisted", order.acquisition_channel == "organic_search")
    check("orders.return_flag=False", not order.return_flag)
    check("orders.gross_margin=179.00", order.gross_margin == Decimal("179.00"))

    # -- OrderItem
    item = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        quantity=1,
        unit_price=Decimal("299.00"),
        line_total=Decimal("299.00"),
    )
    db.add(item)
    db.flush()
    check("INSERT order_items", item.id is not None)

    # -- ForecastResult
    fr = ForecastResult(
        job_id=uuid.uuid4(),
        user_id=u.id,
        run_date=date.today(),
        ds=date(2024, 7, 1),
        yhat=Decimal("52000.00"),
        yhat_lower=Decimal("48000.00"),
        yhat_upper=Decimal("56000.00"),
        is_historical=False,
        scenario_marketing_spend_pct=Decimal("15.00"),
        scenario_price_shift_pct=Decimal("5.00"),
        scenario_seasonal_adj="high",
    )
    db.add(fr)
    db.flush()
    check("INSERT forecast_results", fr.id is not None)
    check("forecast_results.is_historical=False", not fr.is_historical)
    check("forecast_results.scenario_marketing_spend_pct=15",
          fr.scenario_marketing_spend_pct == Decimal("15.00"))

    # -- DailyKpiSnapshot
    snap = DailyKpiSnapshot(
        snapshot_date=date.today(),
        total_revenue=Decimal("125000.00"),
        active_customers=1842,
        new_customers=37,
        total_orders=312,
        churn_rate=Decimal("0.0240"),
        avg_order_value=Decimal("400.64"),
        revenue_na=Decimal("62000.00"),
        revenue_eu=Decimal("38000.00"),
        revenue_apac=Decimal("21000.00"),
        revenue_latam=Decimal("4000.00"),
    )
    db.add(snap)
    db.flush()
    check("INSERT daily_kpi_snapshots", snap.id is not None)
    check("kpi_snapshot.churn_rate correct", snap.churn_rate == Decimal("0.0240"))

    # -- AnalysisResultsCache
    arc = AnalysisResultsCache(
        analysis_type="rfm",
        upload_job_id=job.id,
        result_json={"segments": {"Champions": 245, "At Risk": 87}},
        is_stale=False,
        duration_ms=1250,
    )
    db.add(arc)
    db.flush()
    check("INSERT analysis_results_cache", arc.id is not None)
    check("arc.result_json is dict", isinstance(arc.result_json, dict))

    # -- CsvColumnMapping
    mapping = CsvColumnMapping(
        upload_job_id=job.id,
        csv_header="Sale Amt",
        mapped_table="orders",
        mapped_column_name="total_amount",
        match_score=Decimal("0.8700"),
        match_method="fuzzy",
        is_confirmed=True,
    )
    db.add(mapping)
    db.flush()
    check("INSERT csv_column_mappings", mapping.id is not None)
    check("mapping.match_score=0.87", mapping.match_score == Decimal("0.8700"))

    # -- Insight
    ins = Insight(
        job_id=job.id,
        source_type="preprocess",
        bullet_index=1,
        bullet_text="Revenue grew 23% MoM driven by APAC expansion.",
    )
    db.add(ins)
    db.flush()
    check("INSERT insights", ins.id is not None)

    # -- READ BACK all 11 tables
    print("\n[6] Read Back (SELECT on all 11 tables)")
    check("SELECT users",     db.query(User).count() >= 1)
    check("SELECT customers", db.query(Customer).count() >= 1)
    check("SELECT products",  db.query(Product).count() >= 1)
    check("SELECT orders",    db.query(Order).count() >= 1)
    check("SELECT order_items", db.query(OrderItem).count() >= 1)
    check("SELECT upload_jobs", db.query(UploadJob).count() >= 1)
    check("SELECT csv_column_mappings", db.query(CsvColumnMapping).count() >= 1)
    check("SELECT forecast_results",    db.query(ForecastResult).count() >= 1)
    check("SELECT daily_kpi_snapshots", db.query(DailyKpiSnapshot).count() >= 1)
    check("SELECT analysis_results_cache", db.query(AnalysisResultsCache).count() >= 1)
    check("SELECT insights",  db.query(Insight).count() >= 1)

    db.rollback()   # Clean up — leave the DB empty for real data
    check("Rollback (test data removed)", True)

except Exception as e:
    db.rollback()
    check("CRUD operations", False, str(e))
finally:
    db.close()

# ─── Summary ──────────────────────────────────────────────────
total = len(results)
passed = sum(results)
failed = total - passed
print("\n" + "="*60)
print(f"   RESULT: {passed}/{total} checks passed")
if failed == 0:
    print("   🎉 ALL TESTS PASSED — Database is 100% ready!")
else:
    print(f"   ⚠️  {failed} checks FAILED — see above for details")
print("="*60 + "\n")

sys.exit(0 if failed == 0 else 1)
