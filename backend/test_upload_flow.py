import httpx
import time
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def test_upload():
    print("=== Testing Upload Flow (Step 8) ===")
    
    # 1. Register a fresh user
    print("\n1. Registering test user...")
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    res = httpx.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": "testpassword",
        "full_name": "CSV Test User"
    })
    
    if res.status_code not in (200, 201):
        print(f"Failed to register: {res.text}")
        return
        
    token = res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print(f"User registered successfully. Token obtained.")
    
    # 2. Upload CSV
    print("\n2. Uploading dummy_sales.csv...")
    try:
        with open("dummy_sales.csv", "rb") as f:
            files = {"file": ("dummy_sales.csv", f, "text/csv")}
            res = httpx.post(f"{BASE_URL}/upload/csv", headers=headers, files=files)
    except FileNotFoundError:
        print("dummy_sales.csv not found!")
        return
        
    if res.status_code != 201:
        print(f"Upload failed: {res.status_code} {res.text}")
        return
        
    data = res.json()
    job_id = data.get("job_id")
    print(f"Upload successful! Job ID: {job_id}")
    
    # 3. Poll DB directly to see if Mapping completed
    print("\n3. Waiting for worker to process auto-mapping...")
    import psycopg2
    import os
    
    db_url = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    max_retries = 10
    for i in range(max_retries):
        cursor.execute("SELECT status FROM upload_jobs WHERE id = %s", (job_id,))
        status = cursor.fetchone()[0]
        print(f"[{i+1}/{max_retries}] Job status: {status}")
        
        if status in ("mapping_complete", "failed"):
            break
        time.sleep(1)
        
    if status == "mapping_complete":
        print("\n✅ PASS | Auto-mapping completed successfully!")
        
        cursor.execute("SELECT csv_header, mapped_table, mapped_column, match_score, is_confirmed FROM csv_column_mappings WHERE upload_job_id = %s", (job_id,))
        mappings = cursor.fetchall()
        print(f"Found {len(mappings)} column mappings:")
        for m in mappings:
            print(f"  - '{m[0]}' -> {m[1]}.{m[2]} (Score: {m[3]}, Confirmed: {m[4]})")
    else:
        print("\n❌ FAIL | Job did not complete mapping successfully.")
        
    cursor.close()
    conn.close()

if __name__ == "__main__":
    test_upload()
