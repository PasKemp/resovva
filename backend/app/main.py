"""FastAPI Application – Resovva.de."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import auth, cases, documents, workflows
from app.core.config import get_settings
from app.core.limiter import limiter
from app.infrastructure.database import create_all_tables

settings = get_settings()

app = FastAPI(
    title="Resovva.de",
    description="Intelligenter Fall-Assistent (LegalTech)",
    version="0.1.0",
    on_startup=[create_all_tables],
)

# ── Rate Limiter (Brute-Force-Schutz für /auth/login) ────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS (Frontend auf localhost:5173 in DEV) ─────────────────────────────────
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Pflicht für HttpOnly-Cookie-Auth
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router ────────────────────────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/api/v1")
app.include_router(cases.router,     prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
