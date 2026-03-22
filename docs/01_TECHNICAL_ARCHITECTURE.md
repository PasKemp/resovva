# Technical Architecture & Repository Structure

Dieses Dokument beschreibt die Code-Organisation, den Technologie-Stack und den lokalen Entwicklungs-Workflow für Resovva.de.

Wir nutzen einen **Monorepo-Ansatz**, bei dem Frontend, Backend und Infrastruktur-Code im selben Git-Repository leben. Das garantiert synchrone Deployments und ein reibungsloses lokales Setup.

---

## 1. Repository-Struktur (Tree)

Das Root-Verzeichnis ist in drei logische Hauptbereiche unterteilt: `frontend/`, `backend/` und Infrastruktur/Docs.

```text
resovva/
├── .git/
├── .gitignore
├── README.md
├── docker-compose.yml          # Startet die komplette lokale Dev-Umgebung
├── Jenkinsfile                 # (oder .github/workflows/) CI/CD Pipeline Definition
│
├── docs/                       # Projektdokumentation (PRDs, Vision, Epics)
│   ├── 00_VISION.md
│   ├── 01_TECHNICAL_ARCHITECTURE.md
│   ├── API-DESIGN.md         # API-Entwurf (optional)
│   └── epics/                  # Detaillierte Epics / PRDs
│
├── frontend/                   # SPA: React + Vite + Material-UI
│   ├── package.json
│   ├── vite.config.ts
│   ├── Dockerfile              # Baut das statische Frontend (Nginx)
│   ├── public/
│   └── src/
│       ├── assets/
│       ├── components/         # Wiederverwendbare UI-Elemente
│       ├── features/           # Fachliche Module
│       ├── hooks/
│       ├── services/           # API-Client
│       ├── theme/              # MUI Theme
│       └── App.tsx
│
├── backend/                    # API: Python 3.12 + FastAPI + LangGraph
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── .env.example
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── core/
│   │   ├── domain/
│   │   └── infrastructure/
│   └── tests/
│
└── k8s/                        # Kubernetes Manifeste für Produktion
    ├── frontend-deployment.yaml
    ├── backend-deployment.yaml
    ├── ingress.yaml            # Routing (/api -> Backend, / -> Frontend)
    └── configmaps.yaml
```

---

## 2. Der Technologie-Stack im Detail

### 2.1 Frontend (Client-Side)

- **Core:** React 18+ mit TypeScript
- **Build-Tool:** Vite
- **UI-Library:** Material-UI (MUI)
- **State Management:** Zustand oder React Query
- **Routing:** React Router DOM

### 2.2 Backend (Server-Side)

- **Core:** Python 3.12, FastAPI
- **KI-Orchestrierung:** LangGraph und LangChain
- **LLMs:** OpenAI API / Azure OpenAI für Prod.

### 2.3 Datenbanken & Storage

- **PostgreSQL** für Nutzer, Metadaten, LangGraph-Checkpointer
- **Qdrant** für RAG-Embeddings
- **MinIO** lokal (S3-kompatibel), in Prod z. B. S3 oder Azure Blob

---

## 3. Lokaler Entwicklungs-Workflow

Mit **Docker Desktop:** `docker-compose up --build` im Repository-Root.

- Frontend: http://localhost:5173
- Backend (Swagger): http://localhost:8000/docs

---

## 4. CI/CD & Deployment

1. **Frontend-Build:** Vite → Nginx-Image (z. B. `ghcr.io/resovva/frontend:latest`)
2. **Backend-Build:** Python-Slim-Image (z. B. `ghcr.io/resovva/backend:latest`)

Ingress routet `/api/*` zum Backend und übrigen Traffic zum Frontend.
