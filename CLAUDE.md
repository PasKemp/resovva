# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Resovva is a German LegalTech SaaS (€20/case Pay-per-Use) that helps consumers structure disputes against energy utilities. The core workflow uses an LLM-powered agent to ingest uploaded PDF documents, extract key entities (MaLo ID, meter numbers, amounts, dates), build a chronology, and identify gaps — guiding users through dispute resolution.

## Development Commands

### Full Stack (Recommended)
```bash
docker-compose up --build
```
- Frontend: http://localhost:5173
- Backend API + Swagger: http://localhost:8000/docs
- MinIO Console: http://localhost:9001
- Qdrant: http://localhost:6333

### Backend Only
```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### Testing
```bash
cd backend
pytest tests/ -v

# Single test
pytest tests/test_api.py::test_name -v
```

### Linting
```bash
cd backend
ruff check app
```

## Architecture

### Backend (`backend/app/`)

**FastAPI + LangGraph agent system:**

- `main.py` — app entry point, mounts two routers
- `api/v1/workflows.py` — `POST /api/v1/workflows/run` triggers the LangGraph agent
- `api/v1/documents.py` — `POST /api/v1/documents/upload` stores PDFs to `/tmp/resovva_uploads`
- `agents/graph.py` — compiled LangGraph state machine with 4 nodes: `ingest → extract → chronology → gaps`
- `agents/state.py` — `AgentState` TypedDict (messages, case_id, documents, extracted data)
- `agents/tools/mastr_lookup.py` — queries MaStR API to resolve network operators
- `domain/models/db.py` — SQLAlchemy ORM: `User`, `Case`, `Document`, `ChronologyEvent`
- `domain/models/document.py` — Pydantic models: `ExtractedEntity`, `DocumentInput`
- `domain/services/document_ingest.py` — PDF processing pipeline
- `domain/services/chronology_builder.py` — timeline generation (stub)
- `infrastructure/azure_openai.py` — LLM factory supporting Azure OpenAI (prod) or standard OpenAI (dev)
- `infrastructure/checkpointer.py` — `PostgresSaver` (prod) or `MemorySaver` (dev) for LangGraph state
- `infrastructure/qdrant_client.py` — vector DB initialization
- `core/config.py` — Pydantic Settings loading from environment
- `core/security.py` — PII masking (IBAN, email) via regex or Presidio

**LangGraph threading:** Thread ID = Case ID, enabling per-case state isolation across requests.

**LLM:** GPT-4o with `temperature=0` for deterministic extraction; `with_structured_output()` returns Pydantic models.

### Frontend (`frontend/src/`)

React 18 + TypeScript + Vite + Material-UI. Currently a minimal placeholder (`App.tsx`). Feature directories (`components/`, `features/`, `hooks/`, `services/`, `theme/`) are scaffolded but largely empty.

### Infrastructure

- **PostgreSQL 15** — primary database + optional LangGraph checkpoint store
- **MinIO** — S3-compatible object storage for documents (local dev; S3/Azure Blob in prod)
- **Qdrant** — vector database for document embeddings (`resovva_docs` collection)
- **k8s/** — Kubernetes manifests for production deployment
- **`.github/workflows/ci-cd.yaml`** — GitHub Actions on self-hosted runner: pytest → Docker build → push to GHCR

## Environment Configuration

Copy `backend/.env.example` and fill in:

```
# Dev: standard OpenAI
OPENAI_API_KEY=sk-proj-...

# Prod: Azure OpenAI (DSGVO-compliant)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://....openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
OPENAI_API_VERSION=2024-02-15-preview
```

Key config values (in `core/config.py`):
- `postgres_checkpoint_url` — enables persistent LangGraph state (omit for in-memory dev)
- `ingest_backend` — `"text"` | `"unstructured"` | `"azure"` (PDF parsing strategy)
- `data_retention_days` — defaults to 30 (Privacy-by-Design auto-deletion)
- `USE_PRESIDIO=1` — enables advanced NLP-based PII masking (optional)

## Key Design Decisions

- **Dual LLM support:** `azure_openai.py` returns an `AzureChatOpenAI` or `ChatOpenAI` based on whether `AZURE_OPENAI_API_KEY` is set. This is the single LLM injection point.
- **Privacy-first:** PII (IBANs, emails) is masked in `core/security.py` before any text reaches the LLM.
- **Case status flow:** `DRAFT → WAITING_FOR_USER → PAID → COMPLETED` (defined in `domain/models/db.py`).
- **Unfinished stubs:** `_node_chronology` and `_node_gaps` in `agents/graph.py`, and the `/api/v1/workflows/resume` endpoint are not yet implemented.
- **Embeddings:** disabled/commented in `infrastructure/azure_openai.py` — Qdrant integration is scaffolded but not active.

## Documentation

Full specs in `docs/`:
- `00_VISION.md` — product vision and business model
- `01_TECHNICAL_ARCHITECTURE.md` — architecture reference
- `02_API-DESIGN.md` — complete API specification
- `epics/EPIC1–EPIC6.md` — feature epics
