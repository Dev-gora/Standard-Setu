"""Standard Setu API — FastAPI backend for the SIH26108 procurement engine."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Standard Setu API</title>
                    <style>
                        body { font-family: system-ui, -apple-system, sans-serif; background: #0b0f19; color: #f3f4f6; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                        .card { background: #111827; padding: 2.5rem; border-radius: 1rem; border: 1px solid #1f2937; text-align: center; max-width: 480px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }
                        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #60a5fa; }
                        p { color: #9ca3af; line-height: 1.5; margin-bottom: 1.5rem; }
                        a.btn { display: inline-block; background: #2563eb; color: #ffffff; text-decoration: none; padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: 600; transition: background 0.2s; }
                        a.btn:hover { background: #1d4ed8; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>🏛️ Standard Setu Backend API</h1>
                        <p>You are accessing the raw backend API on port 8000. To launch and use the full web user interface, click below:</p>
                        <a href="http://localhost:3000" class="btn">Open Web App (localhost:3000) &rarr;</a>
                    </div>
                </body>
            </html>
            """
        )
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
