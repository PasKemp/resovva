# Resovva.de Backend – Multi-Stage
#
# dev     – Lokale Entwicklung (Hot-Reload, alle Dev-Deps)
# builder – Intermediate Build Stage für Production
# runtime – Production (minimal, non-root)

# ── Stage 1: Dev (docker-compose) ────────────────────────────────────────────
FROM python:3.12-slim AS dev

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app/ ./app/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev,postgres,llamaparse]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# ── Stage 2: Builder (Production) ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY app/ ./app/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[postgres,llamaparse]"

# ── Stage 3: Runtime (minimal, non-root) ─────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=app:app app/ ./app/
COPY --chown=app:app pyproject.toml ./

USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
