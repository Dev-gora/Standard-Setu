"""Standard Setu API — FastAPI backend for the SIH26108 procurement engine."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import procurement

settings = get_settings()

app = FastAPI(
    title="Standard Setu API",
    description="AI-powered recommendation engine for Indian Standards for procurement specifications (SIH26108)",
    version="2.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(procurement.router)


@app.get("/")
async def root():
    return {
        "name": "Standard Setu API",
        "version": "2.0.0",
        "description": "AI-powered recommendation engine for Indian Standards for procurement specifications",
        "endpoints": {
            "recommend": "POST /api/procure/recommend",
            "clarify": "POST /api/procure/clarify",
            "tender_block": "POST /api/procure/tender-block",
            "bulk_check": "POST /api/procure/bulk-check",
            "standard_detail": "GET /api/procure/standard/{is_number}",
            "evidence": "GET /api/procure/evidence/{is_number}",
            "verify": "POST /api/procure/verify",
            "history": "GET /api/procure/history",
            "watchlist": "GET|POST|DELETE /api/procure/watchlist",
            "notifications": "GET /api/procure/notifications",
            "compare": "POST /api/procure/compare",
            "versions": "GET /api/procure/versions/{is_number}",
            "report": "POST /api/procure/report",
            "registry_meta": "GET /api/procure/meta",
            "health": "GET /health",
        },
    }


@app.get("/health")
async def health():
    from app.services import standards_registry as registry

    return {"status": "healthy", "registry_count": registry.registry_size()}
