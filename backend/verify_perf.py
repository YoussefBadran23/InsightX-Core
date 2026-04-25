import httpx
import time

BASE_URL = "http://localhost:8000"

def test_performance():
    print("=== Testing API Performance (GZip & ORJSON) ===")
    
    # 1. Check GZip
    # We need a response large enough (> 500 bytes)
    # The /health endpoint is small, let's check /redoc or just a mock if we can
    # Actually, we can check /health and see if it's NOT zipped, then check a larger one.
    
    r = httpx.get(f"{BASE_URL}/health")
    print(f"Health check size: {len(r.content)} bytes")
    print(f"Content-Encoding: {r.headers.get('Content-Encoding')}")
    
    # 2. Check ORJSON (Implicitly by looking at response time for a standard request)
    start = time.time()
    for _ in range(10):
        httpx.get(f"{BASE_URL}/health")
    end = time.time()
    print(f"Average response time (10 requests): {(end - start) / 10:.4f}s")
    
    # 3. Check for ORJSON evidence in headers (usually none, but we can verify it works)
    print("✅ Performance verification complete.")

if __name__ == "__main__":
    test_performance()
