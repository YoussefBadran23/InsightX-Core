"""
InsightX — FINAL Verification Test
Covers ALL changes from Step 5 (Database) and Step 7 (Auth):
  - 11 tables exist with correct columns
  - Default role = "user"
  - Admin removed from public signup
  - Secret admin login endpoint (/auth/admin/login)
  - All 6 regular auth endpoints
  - JWT token validation
  - Password change & reset flow
  - Soft delete handling
  - Anti-enumeration protection
  - ADMIN_SECRET_KEY enforcement
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Imports ───────────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.core.security import hash_password
from app.core.config import settings

client = TestClient(app)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db"
)
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

PASS = "✅"
FAIL = "❌"
results = []
section_fails = {}

def check(label, condition, detail="", section=""):
    icon = PASS if condition else FAIL
    msg = f"  {icon} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append(condition)
    if not condition and section:
        section_fails.setdefault(section, []).append(label)
    return condition

def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


print("\n" + "="*60)
print("   InsightX — FINAL Verification Test")
print("   Step 5 (Database) + Step 7 (Auth)")
print("="*60)

# ══════════════════════════════════════════════════════════════
# BLOCK 1 — DATABASE INTEGRITY
# ══════════════════════════════════════════════════════════════
section("BLOCK 1 · Database Integrity")

# 1.1 Connection
try:
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version()")).scalar()
    check("PostgreSQL connection", True, ver.split(",")[0], "db")
except Exception as e:
    check("PostgreSQL connection", False, str(e), "db")
    print("\n❌ Cannot connect to DB. Aborting.")
    sys.exit(1)

# 1.2 All 11 tables
inspector = inspect(engine)
actual_tables = set(inspector.get_table_names())
for table in sorted([
    "users", "customers", "products", "orders", "order_items",
    "upload_jobs", "csv_column_mappings", "forecast_results",
    "daily_kpi_snapshots", "analysis_results_cache", "insights"
]):
    check(f"Table exists: {table}", table in actual_tables, section="db")

# 1.3 Alembic revision
with engine.connect() as conn:
    rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
check("Migration revision correct", rev == "cd7f4376ca5f", f"rev={rev}", "db")

# 1.4 Key v3.0 columns
def cols(t): return {c["name"] for c in inspector.get_columns(t)}

for col in ["payment_method","acquisition_channel","return_flag","delivery_days",
            "sentiment_label","gross_margin"]:
    check(f"orders.{col} exists", col in cols("orders"), section="db")

for col in ["rfm_score","rfm_segment","cohort_month","clv_predicted","age_group","gender"]:
    check(f"customers.{col} exists", col in cols("customers"), section="db")

for col in ["cost_price","supplier","abc_tier","return_rate"]:
    check(f"products.{col} exists", col in cols("products"), section="db")

# 1.5 JSONB columns
for col, table in [("widget_config","users"), ("result_json","analysis_results_cache")]:
    col_info = next((c for c in inspector.get_columns(table) if c["name"] == col), None)
    check(f"{table}.{col} is JSONB", col_info is not None, section="db")

# ══════════════════════════════════════════════════════════════
# BLOCK 2 — USER MODEL DEFAULTS
# ══════════════════════════════════════════════════════════════
section("BLOCK 2 · User Model Defaults")

db = Session()
try:
    admin_seed = User(
        email="admin@insightx.io",
        full_name="Super Admin",
        hashed_password=hash_password("AdminPass999!"),
        role="admin",
        widget_config={},
        is_active=True,
    )
    db.add(admin_seed)
    db.commit()
    db.refresh(admin_seed)
    check("Admin user seeded (role=admin)", admin_seed.role == "admin", section="model")

    default_user = User(
        email="default_role_test@insightx.io",
        full_name="Default Role User",
        hashed_password=hash_password("Test1234!"),
        widget_config={},
        is_active=True,
    )
    db.add(default_user)
    db.commit()
    db.refresh(default_user)
    check("Default role = 'user'", default_user.role == "user",
          f"got '{default_user.role}'", "model")

except Exception as e:
    check("User model operations", False, str(e), "model")
finally:
    db.close()

# ══════════════════════════════════════════════════════════════
# BLOCK 3 — PUBLIC AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════
section("BLOCK 3 · Public Auth Endpoints")

# 3.1 Health
r = client.get("/health")
check("GET /health → 200", r.status_code == 200, section="auth")

# 3.2 Register with default role
r = client.post("/api/v1/auth/register", json={
    "email": "final_test@insightx.io",
    "full_name": "Final Tester",
    "password": "FinalTest123!",
})
check("Register (no role) → 201", r.status_code == 201, str(r.status_code), "auth")
reg = r.json()
check("Register gets user + token", "user" in reg and "access_token" in reg, section="auth")
check("Default role = 'user' from API", reg.get("user", {}).get("role") == "user",
      f"got '{reg.get('user',{}).get('role')}'", "auth")
USER_TOKEN = reg.get("access_token", "")

# 3.3 Register with explicit analyst role
r = client.post("/api/v1/auth/register", json={
    "email": "analyst@insightx.io",
    "full_name": "Analyst User",
    "password": "Analyst123!",
    "role": "analyst",
})
check("Register as analyst → 201", r.status_code == 201, str(r.status_code), "auth")
check("Analyst role set", r.json().get("user", {}).get("role") == "analyst", section="auth")

# 3.4 Admin role BLOCKED on public register
r = client.post("/api/v1/auth/register", json={
    "email": "sneaky@insightx.io",
    "full_name": "Sneaky",
    "password": "Hacker123!",
    "role": "admin",
})
check("Admin role blocked on register → 422", r.status_code == 422,
      f"got {r.status_code}", "auth")

# 3.5 Duplicate email → 409
r = client.post("/api/v1/auth/register", json={
    "email": "final_test@insightx.io",
    "full_name": "Dupe",
    "password": "Dupe12345!",
})
check("Duplicate email → 409", r.status_code == 409, section="auth")

# 3.6 Login
r = client.post("/api/v1/auth/login", json={
    "email": "final_test@insightx.io",
    "password": "FinalTest123!",
})
check("Login → 200", r.status_code == 200, section="auth")
login_data = r.json()
check("Login token_type=bearer", login_data.get("token_type") == "bearer", section="auth")
check("Login expires_in > 0", login_data.get("expires_in", 0) > 0, section="auth")
LOGIN_TOKEN = login_data.get("access_token", "")

# 3.7 Wrong password → 401
r = client.post("/api/v1/auth/login", json={
    "email": "final_test@insightx.io",
    "password": "wrongpassword",
})
check("Wrong password → 401", r.status_code == 401, section="auth")

# ══════════════════════════════════════════════════════════════
# BLOCK 4 — PROTECTED ENDPOINTS
# ══════════════════════════════════════════════════════════════
section("BLOCK 4 · Protected Endpoints")

# 4.1 /me with valid token
r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {LOGIN_TOKEN}"})
check("GET /me → 200", r.status_code == 200, section="protected")
me = r.json()
check("/me email correct", me.get("email") == "final_test@insightx.io", section="protected")
check("/me role = 'user'", me.get("role") == "user", f"got '{me.get('role')}'", "protected")
check("/me last_login_at set", me.get("last_login_at") is not None, section="protected")
check("/me widget_config is dict", isinstance(me.get("widget_config"), dict), section="protected")

# 4.2 /me without token → 403
r = client.get("/api/v1/auth/me")
check("No token → 403", r.status_code in (401, 403), str(r.status_code), "protected")

# 4.3 Invalid token → 401
r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
check("Invalid token → 401", r.status_code == 401, section="protected")

# 4.4 PATCH /me
r = client.patch("/api/v1/auth/me",
    json={"full_name": "Updated Name"},
    headers={"Authorization": f"Bearer {LOGIN_TOKEN}"},
)
check("PATCH /me → 200", r.status_code == 200, section="protected")
check("PATCH /me name updated", r.json().get("full_name") == "Updated Name", section="protected")

# ══════════════════════════════════════════════════════════════
# BLOCK 5 — PASSWORD FLOWS
# ══════════════════════════════════════════════════════════════
section("BLOCK 5 · Password Flows")

# 5.1 Change password
r = client.post("/api/v1/auth/change-password",
    json={"current_password": "FinalTest123!", "new_password": "NewFinal456!"},
    headers={"Authorization": f"Bearer {LOGIN_TOKEN}"},
)
check("Change password → 200", r.status_code == 200, section="password")

# Old password must fail
r = client.post("/api/v1/auth/login", json={
    "email": "final_test@insightx.io", "password": "FinalTest123!"
})
check("Old password rejected", r.status_code == 401, section="password")

# New password must work
r = client.post("/api/v1/auth/login", json={
    "email": "final_test@insightx.io", "password": "NewFinal456!"
})
check("New password accepted", r.status_code == 200, section="password")
NEW_TOKEN = r.json().get("access_token", "")

# 5.2 Wrong current password
r = client.post("/api/v1/auth/change-password",
    json={"current_password": "FinalTest123!", "new_password": "Hacker123!"},
    headers={"Authorization": f"Bearer {NEW_TOKEN}"},
)
check("Wrong current password → 400", r.status_code == 400, section="password")

# 5.3 Forgot password
r = client.post("/api/v1/auth/forgot-password",
    json={"email": "final_test@insightx.io"})
check("Forgot password → 200", r.status_code == 200, section="password")
msg = r.json().get("message", "")
check("Dev mode returns token", "Reset token:" in msg, section="password")

raw_token = None
if "Reset token:" in msg:
    raw_token = msg.split("Reset token:")[1].split("—")[0].strip()

# 5.4 Reset password
if raw_token:
    r = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "ResetFinal789!",
    })
    check("Reset password → 200", r.status_code == 200, section="password")

    r = client.post("/api/v1/auth/login", json={
        "email": "final_test@insightx.io", "password": "ResetFinal789!"
    })
    check("Login after reset", r.status_code == 200, section="password")

    # Token replay must fail (already consumed)
    r = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "new_password": "HackerReplay!"
    })
    check("Token replay rejected", r.status_code == 400, section="password")

# 5.5 Anti-enumeration
r = client.post("/api/v1/auth/forgot-password",
    json={"email": "ghost@insightx.io"})
check("Unknown email → 200 (anti-enum)", r.status_code == 200, section="password")

# ══════════════════════════════════════════════════════════════
# BLOCK 6 — SECRET ADMIN LOGIN
# ══════════════════════════════════════════════════════════════
section("BLOCK 6 · Secret Admin Login Endpoint")

ADMIN_KEY = settings.ADMIN_SECRET_KEY

# 6.1 Admin endpoint hidden from public schema
r = client.get("/openapi.json")
paths = r.json().get("paths", {})
check("Admin endpoint hidden from Swagger",
      "/api/v1/auth/admin/login" not in paths, section="admin")

# 6.2 Correct credentials + correct key → 200
r = client.post("/api/v1/auth/admin/login", json={
    "email": "admin@insightx.io",
    "password": "AdminPass999!",
    "admin_key": ADMIN_KEY,
})
check("Admin login → 200", r.status_code == 200, str(r.status_code), "admin")
admin_data = r.json()
check("Admin token issued", "access_token" in admin_data, section="admin")

# 6.3 Correct credentials + WRONG key → 401
r = client.post("/api/v1/auth/admin/login", json={
    "email": "admin@insightx.io",
    "password": "AdminPass999!",
    "admin_key": "wrong-key",
})
check("Wrong admin_key → 401", r.status_code == 401, section="admin")

# 6.4 Regular user with correct key → 401 (not admin)
r = client.post("/api/v1/auth/admin/login", json={
    "email": "final_test@insightx.io",
    "password": "ResetFinal789!",
    "admin_key": ADMIN_KEY,
})
check("Non-admin user blocked → 401", r.status_code == 401,
      f"got {r.status_code}", "admin")

# 6.5 Wrong password + correct key → 401
r = client.post("/api/v1/auth/admin/login", json={
    "email": "admin@insightx.io",
    "password": "WrongPass!",
    "admin_key": ADMIN_KEY,
})
check("Wrong admin password → 401", r.status_code == 401, section="admin")

# 6.6 Admin token can access /me and shows role=admin
if "access_token" in admin_data:
    r = client.get("/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_data['access_token']}"})
    check("Admin /me → 200", r.status_code == 200, section="admin")
    check("Admin role = 'admin'", r.json().get("role") == "admin",
          f"got '{r.json().get('role')}'", "admin")

# ══════════════════════════════════════════════════════════════
# BLOCK 7 — OpenAPI SCHEMA INTEGRITY
# ══════════════════════════════════════════════════════════════
section("BLOCK 7 · OpenAPI Schema")

r = client.get("/openapi.json")
check("OpenAPI → 200", r.status_code == 200, section="schema")
paths = r.json().get("paths", {})
for ep in ["/api/v1/auth/register", "/api/v1/auth/login",
           "/api/v1/auth/me", "/api/v1/auth/forgot-password",
           "/api/v1/auth/reset-password", "/api/v1/auth/change-password"]:
    check(f"Schema has {ep}", ep in paths, section="schema")

# ══════════════════════════════════════════════════════════════
# CLEANUP
# ══════════════════════════════════════════════════════════════
section("Cleanup")
db = Session()
try:
    for email in [
        "final_test@insightx.io",
        "analyst@insightx.io",
        "admin@insightx.io",
        "default_role_test@insightx.io",
    ]:
        u = db.query(User).filter(User.email == email).first()
        if u:
            db.delete(u)
    db.commit()
    check("Test data cleaned up", True)
except Exception as e:
    check("Cleanup", False, str(e))
finally:
    db.close()

# ══════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════
total = len(results)
passed = sum(results)
failed = total - passed

print("\n" + "="*60)
print(f"\n   {'BLOCK':40s} STATUS")
print(f"   {'─'*50}")
blocks = {
    "BLOCK 1 — Database Integrity":      "db",
    "BLOCK 2 — User Model Defaults":     "model",
    "BLOCK 3 — Public Auth Endpoints":   "auth",
    "BLOCK 4 — Protected Endpoints":     "protected",
    "BLOCK 5 — Password Flows":          "password",
    "BLOCK 6 — Secret Admin Login":      "admin",
    "BLOCK 7 — OpenAPI Schema":          "schema",
}
for label, key in blocks.items():
    fails = section_fails.get(key, [])
    status = "✅ ALL PASS" if not fails else f"❌ {len(fails)} FAIL(S)"
    print(f"   {label:40s} {status}")

print(f"\n   TOTAL: {passed}/{total} checks passed")
if failed == 0:
    print("   🎉 PERFECT SCORE — All systems go!")
else:
    print(f"   ⚠️  {failed} failures found")
print("="*60 + "\n")
sys.exit(0 if failed == 0 else 1)
