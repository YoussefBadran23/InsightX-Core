"""InsightX — FastAPI Application Entrypoint."""

import logging
import time
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

from app.routers import auth, upload, jobs, analytics, kpi, customers, products, forecasts, insights  # noqa: E402

# Rate limiter — keyed by client IP; shared across routers via app.state
limiter = Limiter(key_func=get_remote_address)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("insightx.api")

app = FastAPI(
    title="InsightX API",
    description="AI-powered SaaS analytics platform — backend gateway.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=ORJSONResponse,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Rate Limiting Middleware ───────────────────────────────────────────────
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/v1/jobs"):
        return await limiter.limit("30/minute")(call_next)(request)
    else:
        return await limiter.limit("200/day")(call_next)(request)

# ── CORS Middleware ───────────────────────────────────────────────────────────
def get_allowed_origins():
    origins = ["http://localhost:3000"]
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)
    return origins

_origins = get_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── GZip Middleware ───────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=500)

# ── Request logging middleware ───────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %s %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/api/v1")
app.include_router(upload.router,    prefix="/api/v1")
app.include_router(jobs.router,      prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(kpi.router,       prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(products.router,  prefix="/api/v1")
app.include_router(forecasts.router, prefix="/api/v1")
app.include_router(insights.router,  prefix="/api/v1")

# ── System endpoints ───────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    """Liveness probe — returns 200 when the API is up."""
    return {"status": "ok", "service": "insightx-backend", "version": "2.0.0"}
