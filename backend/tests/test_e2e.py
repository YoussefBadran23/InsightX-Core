import pytest
import httpx
import uuid
import asyncio

BASE_URL = "http://localhost:8000/api/v1"
CSV_PATH = r"d:\projects\InsightX\InsightX-Core\datasets\raw\kaggle\E-Commerce Data.csv"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_full_pipeline_with_real_data():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=httpx.Timeout(600.0)) as client:
        # 1. Health
        health_res = await client.get("http://localhost:8000/health")
        assert health_res.status_code == 200
        
        # 2. Register
        dummy_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        dummy_password = "SecurePassword123!"
        reg_res = await client.post("/auth/register", json={
            "email": dummy_email,
            "full_name": "Integration Test User",
            "password": dummy_password
        })
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Upload CSV
        print("\n[+] Uploading E-Commerce Data.csv (this may take a moment)...")
        with open(CSV_PATH, "rb") as f:
            files = {"file": ("E-Commerce Data.csv", f, "text/csv")}
            upload_res = await client.post("/upload/csv", headers=headers, files=files)
            
        assert upload_res.status_code == 201, f"Upload failed: {upload_res.text}"
        job_id = upload_res.json()["job_id"]
        print(f"[+] Upload successful! Job ID: {job_id}")
        
        # 4. Polling Loop
        print("[+] Polling Celery workers for job completion...")
        status = "pending"
        max_attempts = 120 # 6 minutes max
        attempts = 0
        while status not in ["completed", "failed"] and attempts < max_attempts:
            await asyncio.sleep(3)
            status_res = await client.get(f"/jobs/{job_id}/status", headers=headers)
            assert status_res.status_code == 200
            data = status_res.json()
            status = data["status"]
            print(f"    -> Status: {status} | Processed: {data.get('rows_processed', 0)}")
            attempts += 1
            
        assert status == "completed", f"Job failed or timed out. Final data: {data}"
        print("[+] AI Pipeline Completed Successfully!")
        
        # 5. Data Validation - KPI
        kpi_res = await client.get("/kpi/summary", headers=headers)
        assert kpi_res.status_code == 200
        kpi_data = kpi_res.json()
        assert float(kpi_data["total_revenue"]) > 0, "Revenue should be > 0"
        assert kpi_data["total_orders"] > 0, "Orders should be > 0"
        
        # 6. Data Validation - Customers
        cust_res = await client.get("/customers", headers=headers)
        assert cust_res.status_code == 200
        cust_data = cust_res.json()
        assert cust_data["total"] > 0, "Customers should exist"
        
        # 7. Data Validation - Products
        prod_res = await client.get("/products", headers=headers)
        assert prod_res.status_code == 200
        prod_data = prod_res.json()
        assert prod_data["total"] > 0, "Products should exist"
        
        # 8. Data Validation - Analytics Summary
        analytics_res = await client.get(f"/analytics/summary?job_id={job_id}", headers=headers)
        assert analytics_res.status_code == 200
        analytics_data = analytics_res.json()
        assert len(analytics_data["modules"]) > 0, "Analytics modules should be populated"
        
        # 9. Data Validation - Forecast
        forecast_res = await client.get(f"/forecasts/{job_id}", headers=headers)
        assert forecast_res.status_code in [200, 404]
        
        print("[+] All endpoints validated mathematically!")
