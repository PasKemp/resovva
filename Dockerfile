# Resovva.ai – Multi-Stage, Non-Root
# Stage 1: Build (Dependencies)
FROM python:3.12-slim AS builder

WORKDIR /app

# System-Abhängigkeiten nur für Build (z.B. wenn Pakete kompilieren)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Virtuelle Umgebung und Abhängigkeiten
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY app/ ./app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Stage 2: Runtime (minimal, non-root)
FROM python:3.12-slim AS runtime

WORKDIR /app

# Nur Laufzeit-Systempakete (z.B. für PDF/OCR später: poppler-utils, tesseract)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Nutzer ohne Root-Rechte
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Venv aus Builder übernehmen
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# App-Code (als app:app besitzen)
COPY --chown=app:app app/ ./app/
COPY --chown=app:app pyproject.toml ./
# .env in Prod über Mount/Secrets oder Umgebungsvariablen bereitstellen

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
