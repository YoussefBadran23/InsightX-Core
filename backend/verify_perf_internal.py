import httpx
import time
import asyncio

BASE_URL = "http://localhost:8000"

async def test_performance():
    print("=== Testing API Performance (GZip & ORJSON) ===")
    
    async with httpx.AsyncClient() as client:
        # 1. Check GZip
        try:
            r = await client.get(f"{BASE_URL}/docs")
            print(f"Docs page size: {len(r.content)} bytes")
            # Note: httpx automatically decompresses. To check for Gzip, look at 'x-encoded-content-length' or similar if middleware adds it,
            # or check headers if 'Content-Encoding' is preserved.
            print(f"Content-Encoding: {r.headers.get('Content-Encoding')}")
        except Exception as e:
            print(f"GZip check failed: {e}")
        
        # 2. Check response time (ORJSON speed)
        latencies = []
        for _ in range(20):
            t0 = time.perf_counter()
            await client.get(f"{BASE_URL}/health")
            latencies.append(time.perf_counter() - t0)
        
        avg_lat = sum(latencies) / len(latencies)
        print(f"Average response time (20 requests): {avg_lat:.5f}s")
    
    print("✅ Performance verification complete.")

if __name__ == "__main__":
    asyncio.run(test_performance())
