"""InsightX — FastAPI Application Entrypoint."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.routers import auth  # noqa: E402

app = FastAPI(
    title="InsightX API",
    description="AI-powered SaaS analytics platform — backend gateway.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
_origins = [
    "http://localhost:3000",               # Next.js dev server
    os.getenv("FRONTEND_URL", ""),         # Production Vercel URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in _origins if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")

# ── System endpoints ───────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    """Liveness probe — returns 200 when the API is up."""
    return {"status": "ok", "service": "insightx-backend", "version": "2.0.0"}
