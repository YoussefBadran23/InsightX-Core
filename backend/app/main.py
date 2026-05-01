"""InsightX — FastAPI Application Entrypoint."""

import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
import sentry_sdk
from ddtrace import patch_all, tracer

from app.core.config import settings
from app.database import get_db
from app.routers import auth, upload, jobs, analytics, kpi, customers, products, forecasts, insights

# Rate limiter — keyed by client IP; shared across routers via app.state
limiter = Limiter(key_func=get_remote_address)

# Determine logging level based on environment variable
LOG_LEVEL = settings.LOG_LEVEL.upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("insightx.api")

# Initialize Sentry for error tracking
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        traces_sample_rate=1.0,
    )

# Initialize Datadog for monitoring
if settings.DD_API_KEY:
    patch_all()
    tracer.configure(
        hostname="datadog-agent",
        port=8126,
        service=settings.DD_SERVICE,
        env=settings.DD_ENV,
    )

# ── Lifespan (Pre-warming connections) ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Test DB connection
    from app.database import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection established.")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

    yield

    # Shutdown: Dispose engine
    engine.dispose()
    logger.info("Database connections closed.")

app = FastAPI(
    title="InsightX API",
    description="AI-powered SaaS analytics platform — backend gateway.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=ORJSONResponse,
    lifespan=lifespan, # Added lifespan manager
    root_path="", # Set this if Nginx strips prefixes
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS Middleware ───────────────────────────────────────────────────────────
def get_allowed_origins():
    origins = ["http://localhost:3000"]
    frontend_url = settings.FRONTEND_URL
    if frontend_url:
        origins.append(frontend_url)
    return origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"], # Simplified to allow all for standard REST
    allow_headers=["*"], # Prevents annoying CORS preflight blocks
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
async def health_check(db: Session = Depends(get_db)):
    """Liveness probe — returns 200 when the API and DB are up."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "insightx-backend", "version": "2.0.0", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")