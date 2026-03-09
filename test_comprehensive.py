import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1/auth"

def print_result(name, res, expected_status):
    status = "✅ PASS" if res.status_code == expected_status else f"❌ FAIL (Expected {expected_status}, got {res.status_code})"
    print(f"{status} | {name}")
    if res.status_code != expected_status:
        try:
            print(f"       Response: {res.json()}")
        except:
            print(f"       Response: {res.text}")

print("=== STARTING COMPREHENSIVE EDGE-CASE TESTING ===\n")

# 1. Base User Parameters
user_data = {
  "email": "Youssef_m10239@cic-cairo.com",
  "full_name": "YoussefBadran",
  "password": "Test@2003",
  "role": "user" # Note: role 'user' isn't technically in our enum ('admin' | 'analyst' | 'viewer'), but VARCHAR doesn't explicitly restrict without a CHECK, let's see!
}

# Clean database of this user if exists via a secret backdoor or just create a unique one
unique_email = f"test_{uuid.uuid4().hex[:6]}@example.com"
user_data_unique = user_data.copy()
user_data_unique["email"] = unique_email

print("--- 1. HAPPY PATH: Standard Registration & Login ---")
# Register Target User
res = requests.post(f"{BASE_URL}/register", json=user_data_unique)
print_result("Register New User", res, 201)
access_token = res.json().get("access_token") if res.status_code == 201 else None

# Login Target User
res = requests.post(f"{BASE_URL}/login", json={"email": unique_email, "password": "Test@2003"})
print_result("Login Existent User", res, 200)

print("\n--- 2. EDGE CASES: Registration ---")
# Duplicate Email
res = requests.post(f"{BASE_URL}/register", json=user_data_unique)
print_result("Duplicate Email Registration (Should 409)", res, 409)

# Missing Required Fields (Pydantic Validation Check)
missing_fields = {"email": "bad@email.com"}
res = requests.post(f"{BASE_URL}/register", json=missing_fields)
print_result("Missing Required Fields (Should 422)", res, 422)

# Invalid Email Format
bad_email = user_data.copy()
bad_email["email"] = "not-an-email-address"
res = requests.post(f"{BASE_URL}/register", json=bad_email)
print_result("Invalid Email Format (Should 422)", res, 422)

# SQL Injection Attempt in Name
sql_inject = user_data.copy()
sql_inject["email"] = f"sql_{uuid.uuid4().hex[:6]}@test.com"
sql_inject["full_name"] = "Robert'; DROP TABLE users;--"
res = requests.post(f"{BASE_URL}/register", json=sql_inject)
print_result("SQL Injection Defense (Should 201, safely parameterized)", res, 201)

print("\n--- 3. EDGE CASES: Login & Authentication ---")
# Wrong Password
res = requests.post(f"{BASE_URL}/login", json={"email": unique_email, "password": "WrongPassword!"})
print_result("Login with Wrong Password (Should 401)", res, 401)

# Non-existent Email
res = requests.post(f"{BASE_URL}/login", json={"email": "nobody@doesnotexist.com", "password": "Test@2003"})
print_result("Login with Unknown Email (Should 401)", res, 401)

# Missing JWT Token
res = requests.get(f"{BASE_URL}/me")
print_result("Access Protected Route without JWT (Should 401)", res, 401)

# Invalid/Forged JWT Token
headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.token"}
res = requests.get(f"{BASE_URL}/me", headers=headers)
print_result("Access Protected Route with Forged JWT (Should 401)", res, 401)

print("\n--- 4. FULL LIFECYCLE: Authenticated Actions ---")
if access_token:
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Get Profile
    res = requests.get(f"{BASE_URL}/me", headers=headers)
    print_result("Fetch Profile '/me'", res, 200)
    
    # Update Profile
    update_data = {"full_name": "Youssef Badran (Updated)"}
    res = requests.patch(f"{BASE_URL}/me", json=update_data, headers=headers)
    print_result("Update Profile Name", res, 200)
    
    # Try updating protected field (email should not patch here)
    res = requests.patch(f"{BASE_URL}/me", json={"email": "hacked@email.com"}, headers=headers)
    # The API just ignores non-allowed fields in our implementation, so it returns 200 but doesn't change it.
    profile = requests.get(f"{BASE_URL}/me", headers=headers).json()
    if profile.get("email") == unique_email:
        print("✅ PASS | Immutable Field Protection (Email did not change)")
    else:
        print("❌ FAIL | Immutable Field Protection (Email was hacked)")
else:
    print("Skipped authenticated actions, failed to get token.")
    
print("\n=== TESTING COMPLETE ===")
