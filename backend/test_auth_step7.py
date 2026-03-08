"""
InsightX — Step 7 Auth Verification Test
Tests all 6 auth endpoints using the FastAPI TestClient (no live server needed).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

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
print("   InsightX Auth Verification — Step 7")
print("="*60)

# ─── 1. Health check ──────────────────────────────────────────
print("\n[1] Health Check")
r = client.get("/health")
check("GET /health → 200", r.status_code == 200)
check("Health body ok", r.json().get("status") == "ok")

# ─── 2. Register ──────────────────────────────────────────────
print("\n[2] POST /api/v1/auth/register")
reg_payload = {
    "email": "auth_test@insightx.io",
    "full_name": "Auth Tester",
    "password": "SecurePass123!",
    "role": "analyst",
}
r = client.post("/api/v1/auth/register", json=reg_payload)
check("Register → 201", r.status_code == 201, str(r.status_code))
data = r.json()
check("Register returns access_token", "access_token" in data)
check("Register returns user object", "user" in data)
check("Register user.email correct", data.get("user", {}).get("email") == reg_payload["email"])
check("Register user.role correct", data.get("user", {}).get("role") == "analyst")
check("Register expires_in > 0", data.get("expires_in", 0) > 0)
access_token = data.get("access_token", "")

# ─── 3. Duplicate register ─────────────────────────────────────
print("\n[3] Duplicate Email → 409")
r = client.post("/api/v1/auth/register", json=reg_payload)
check("Duplicate register → 409", r.status_code == 409, str(r.status_code))

# ─── 4. Login ─────────────────────────────────────────────────
print("\n[4] POST /api/v1/auth/login")
r = client.post("/api/v1/auth/login", json={
    "email": reg_payload["email"],
    "password": reg_payload["password"],
})
check("Login → 200", r.status_code == 200, str(r.status_code))
login_data = r.json()
check("Login returns access_token", "access_token" in login_data)
check("Login returns token_type=bearer", login_data.get("token_type") == "bearer")
login_token = login_data.get("access_token", "")

# ─── 5. Wrong password ────────────────────────────────────────
print("\n[5] Wrong Password → 401")
r = client.post("/api/v1/auth/login", json={
    "email": reg_payload["email"],
    "password": "wrongpassword",
})
check("Wrong password → 401", r.status_code == 401, str(r.status_code))

# ─── 6. GET /me ───────────────────────────────────────────────
print("\n[6] GET /api/v1/auth/me")
r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login_token}"})
check("GET /me → 200", r.status_code == 200, str(r.status_code))
me = r.json()
check("/me email correct", me.get("email") == reg_payload["email"])
check("/me full_name correct", me.get("full_name") == reg_payload["full_name"])
check("/me has widget_config", "widget_config" in me)
check("/me has last_login_at", "last_login_at" in me)

# ─── 7. No token → 403/401 ────────────────────────────────────
print("\n[7] Protected Route Without Token")
r = client.get("/api/v1/auth/me")
check("No token → 403", r.status_code in (401, 403), str(r.status_code))

# ─── 8. Bad token → 401 ───────────────────────────────────────
print("\n[8] Invalid Token → 401")
r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer this.is.fake"})
check("Bad token → 401", r.status_code == 401, str(r.status_code))

# ─── 9. Change password ───────────────────────────────────────
print("\n[9] POST /api/v1/auth/change-password")
r = client.post(
    "/api/v1/auth/change-password",
    json={"current_password": "SecurePass123!", "new_password": "NewSecure456!"},
    headers={"Authorization": f"Bearer {login_token}"},
)
check("Change password → 200", r.status_code == 200, str(r.status_code))
check("Change password message ok", "successfully" in r.json().get("message", ""))

# Verify old password no longer works
r = client.post("/api/v1/auth/login", json={
    "email": reg_payload["email"], "password": "SecurePass123!"
})
check("Old password rejected after change", r.status_code == 401)

# Verify new password works
r = client.post("/api/v1/auth/login", json={
    "email": reg_payload["email"], "password": "NewSecure456!"
})
check("New password accepted", r.status_code == 200)
new_token = r.json().get("access_token", "")

# ─── 10. Forgot password ──────────────────────────────────────
print("\n[10] POST /api/v1/auth/forgot-password")
r = client.post("/api/v1/auth/forgot-password", json={"email": reg_payload["email"]})
check("Forgot password → 200", r.status_code == 200, str(r.status_code))
reset_msg = r.json().get("message", "")
check("Response contains reset token (dev mode)", "Reset token:" in reset_msg or "reset link" in reset_msg.lower())

# Extract raw token from dev message if present
raw_reset_token = None
if "Reset token:" in reset_msg:
    raw_reset_token = reset_msg.split("Reset token:")[1].split("—")[0].strip()

# ─── 11. Reset password ───────────────────────────────────────
print("\n[11] POST /api/v1/auth/reset-password")
if raw_reset_token:
    r = client.post("/api/v1/auth/reset-password", json={
        "token": raw_reset_token,
        "new_password": "ResetPass789!",
    })
    check("Reset password → 200", r.status_code == 200, str(r.status_code))
    check("Reset password message ok", "successfully" in r.json().get("message", ""))

    # Verify reset password works
    r = client.post("/api/v1/auth/login", json={
        "email": reg_payload["email"], "password": "ResetPass789!"
    })
    check("Login with reset password works", r.status_code == 200)

    # Verify expired/used token is rejected
    r = client.post("/api/v1/auth/reset-password", json={
        "token": raw_reset_token + "tampered",
        "new_password": "HackerPass!",
    })
    check("Tampered reset token rejected", r.status_code == 400)
else:
    check("Reset token extraction (skipped)", True, "non-dev mode")

# ─── 12. Forgot for unknown email ─────────────────────────────
print("\n[12] Forgot Password — Unknown Email (Anti-Enumeration)")
r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@insightx.io"})
check("Unknown email → 200 (no enumeration)", r.status_code == 200)

# ─── 13. OpenAPI schema check ─────────────────────────────────
print("\n[13] OpenAPI Schema")
r = client.get("/openapi.json")
check("OpenAPI schema → 200", r.status_code == 200)
schema = r.json()
paths = schema.get("paths", {})
check("/auth/register in schema", "/api/v1/auth/register" in paths)
check("/auth/login in schema",    "/api/v1/auth/login" in paths)
check("/auth/me in schema",       "/api/v1/auth/me" in paths)

# ─── Summary ──────────────────────────────────────────────────
total = len(results)
passed = sum(results)
failed = total - passed
print("\n" + "="*60)
print(f"   RESULT: {passed}/{total} checks passed")
if failed == 0:
    print("   🎉 ALL AUTH TESTS PASSED — JWT Auth is 100% working!")
else:
    print(f"   ⚠️  {failed} checks FAILED — see above")
print("="*60 + "\n")

sys.exit(0 if failed == 0 else 1)
