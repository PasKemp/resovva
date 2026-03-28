"""
Main entry point for the Resovva FastAPI application.

Configures middleware, exception handlers, and API routers.
Establishes a centralized logging system and integrates observability tools.
"""

from __future__ import annotations

import logging
import logging.config
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import (
    auth, cases, checkout, documents, dossier,
    mobile_upload, timeline, users, workflows
)
from app.core.config import get_settings
from app.core.limiter import limiter
from app.domain.exceptions import ResovvaError
from app.infrastructure.database import create_all_tables

settings = get_settings()

# ── Logging Configuration ─────────────────────────────────────────────────────

def setup_logging() -> None:
    """
    Initialize structured logging.
    
    Uses JSON format in non-development environments for better log analysis.
    """
    is_dev = os.getenv("ENV", "development").lower() == "development"
    
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "json": {
                "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "extra": "%(extra)s"}',
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default" if is_dev else "json",
                "stream": sys.stdout,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
        },
    }
    logging.config.dictConfig(log_config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application startup and shutdown events.
    
    Initializes database tables on startup.
    """
    setup_logging()
    # Ensure tables are created (using migrations is preferred in production)
    create_all_tables()
    yield


# ── App Initialization ────────────────────────────────────────────────────────

app = FastAPI(
    title="Resovva.de API",
    description="Intelligent AI-Assistant for Legal Case Management (LegalTech)",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Rate Limiting (Brute-Force Protection) ────────────────────────────────────

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Exception Handling (Business Logic) ───────────────────────────────────────

@app.exception_handler(ResovvaError)
async def resovva_error_handler(request: Request, exc: ResovvaError) -> JSONResponse:
    """
    Global handler for custom domain exceptions.
    
    Maps internal ResovvaErrors to appropriate HTTP responses.
    """
    logging.getLogger("app.main").warning(
        "Application error occurred",
        extra={"error_code": exc.status_code, "detail": exc.detail}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "detail": exc.detail},
    )


# ── Middleware (Security & CORS) ──────────────────────────────────────────────

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Inject security-hardening HTTP headers into every response.
    
    Includes HSTS, CSP (limited to API needs), and framing protections.
    """
    response = await call_next(request)
    # HSTS: 1 year (only relevant for HTTPS)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # Basic CSP for API (prevent most injections)
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'self';"
    )
    return response


origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Required for HttpOnly-Cookie Auth
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Router Integration ───────────────────────────────────────────────────────

api_prefix = "/api/v1"

# Standardizing inclusion of all domain routers
app.include_router(auth.router,          prefix=api_prefix)
app.include_router(cases.router,         prefix=api_prefix)
app.include_router(checkout.router,      prefix=api_prefix)
app.include_router(documents.router,     prefix=api_prefix)
app.include_router(dossier.router,       prefix=api_prefix)
app.include_router(mobile_upload.router, prefix=api_prefix)
app.include_router(timeline.router,      prefix=api_prefix)
app.include_router(users.router,         prefix=api_prefix)
app.include_router(workflows.router,     prefix=api_prefix)


# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, str]:
    """Basic health check for load balancers and monitoring."""
    return {"status": "ok"}
