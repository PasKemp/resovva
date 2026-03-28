# Resovva.de

**KI-gestützter LegalTech-Service** – hilft Verbrauchern bei Streitigkeiten mit Energieversorgern.

---

## Inhaltsverzeichnis

1. [Produkt](#1-produkt)
2. [Implementierungsstand](#2-implementierungsstand)
3. [Stack](#3-stack)
4. [Lokale Entwicklung](#4-lokale-entwicklung)
5. [Tests](#5-tests)
6. [Dokumentation](#6-dokumentation)

---

## 1. Produkt

Resovva führt Nutzer durch Streitigkeiten mit Stromanbietern und Netzbetreibern (Abrechnungsfehler, PV-Probleme, Anbieterwechsel). Der KI-Agent analysiert hochgeladene Dokumente, baut eine Chronologie auf, identifiziert Lücken und generiert ein professionelles Beschwerde-Dossier für Behörden oder Schlichtungsstellen.

**Preismodell:** 20 € pro Fall (Pay-per-Case).

### Kern-Workflow

| Schritt | Beschreibung |
| --- | --- |
| **1. Ingestion** | PDF-Upload → Textextraktion (pypdf → Azure Fallback) |
| **2. PII-Masking** | IBAN, E-Mail vor LLM-Transfer schwärzen |
| **3. Entitäten-Extraktion** | MaLo-ID, Zählernummer, Beträge, Daten per GPT-4o |
| **4. Chronologie** | Zeitlicher Ablauf aus allen Dokumenten |
| **5. Gap-Analysis** | Fehlende Belege identifizieren, Nutzer um Ergänzung bitten |
| **6. Dossier** | Strukturiertes PDF-Dossier für Schlichtungsstellen |

---

## 2. Implementierungsstand

| Epic | Beschreibung | Status |
| --- | --- | --- |
| **Epic 1** | Auth, Sessions, Multi-Case Dashboard, DSGVO Hard-Delete | ✅ Vollständig |
| **Epic 2** | Dokument-Upload, OCR, PII-Masking, QR-Code-Upload | ✅ Vollständig |
| **Epic 3** | LangGraph-Agent, RAG, Entitäten-Extraktion, MaStR-Lookup, HiTL | ✅ Vollständig |
| **Epic 4** | Chronologie-Aufbau, Gap-Analysis, Nutzer-Feedback-Loop | ✅ Vollständig |
| **Epic 5** | Stripe-Zahlung (Pay-per-Case), Paywall-UI, Retry-Flow | ✅ Vollständig |
| **Epic 6** | PDF-Dossier-Generierung & Beweismittel-Kompilierung | ✅ Vollständig |

---

## 3. Stack

### Backend

- **Python 3.12+** · **FastAPI** · **SQLAlchemy** · **PostgreSQL 15**
- **LangGraph** – stateful KI-Agent (Knoten: ingest → extract → chronology → gaps)
- **GPT-4o** – Azure OpenAI (Produktion, DSGVO) · Standard OpenAI (Entwicklung)
- **WeasyPrint & ReportLab** – Professionelle PDF-Generierung & Stamping
- **Qdrant** – Vektordatenbank für Dokument-Embeddings
- **MinIO** – S3-kompatibler Objektspeicher (lokal); AWS S3 / Azure Blob (Produktion)

### Frontend

- **React 18** · **TypeScript** · **Vite** · **Material-UI**
- **Vitest & MSW** – Umfassende Testing-Infrastruktur

### DevOps

- **Docker Compose** – lokale Entwicklungsumgebung
- **Kubernetes** – Produktions-Deployment (`k8s/`)
- **GitHub Actions** – CI/CD (pytest/vitest → Docker Build → Push zu GHCR)

---

## 4. Lokale Entwicklung

### Voraussetzungen

- **Docker Desktop**
- **Python 3.12+** und **Node.js 20+** (für lokale Entwicklung ohne Docker)

---

### Option A: Kompletter Stack via Docker Compose

```bash
docker-compose up --build
```

Alle Dienste starten automatisch. Tabellen werden beim ersten Backend-Start angelegt.

---

### Option B: Infrastruktur via Docker + Backend lokal (empfohlen)

**Schritt 1** – Infrastruktur starten:

```bash
docker-compose up postgres minio qdrant
```

**Schritt 2** – Python-Umgebung einrichten:

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate        # Windows: ..\.venv\Scripts\activate
pip install -e ".[dev,postgres]"
```

**Schritt 3** – `.env` anlegen:

```bash
cp .env.example .env
# OPENAI_API_KEY eintragen
```

**Schritt 4** – Backend starten:

```bash
uvicorn app.main:app --reload
```

**Schritt 5** – Frontend starten (separates Terminal):

```bash
cd ../frontend
npm install
npm run dev
```

---

### Dienste & URLs

| Dienst | URL | Zugangsdaten |
| --- | --- | --- |
| **Frontend** | <http://localhost:5173> | – |
| **Backend API** | <http://localhost:8000> | – |
| **Swagger / Docs** | <http://localhost:8000/docs> | – |
| **PostgreSQL** | localhost:5432 | `resovva` / `password` |
| **MinIO S3 API** | <http://localhost:9000> | `minioadmin` / `minioadmin` |
| **MinIO Console** | <http://localhost:9001> | `minioadmin` / `minioadmin` |
| **Qdrant Dashboard** | <http://localhost:6333/dashboard> | – |

---

## 5. Tests

### Backend Tests (pytest)

Voraussetzung: PostgreSQL läuft (via Docker Compose). Die Test-DB `resovva_test` wird automatisch angelegt.

```bash
cd backend
# Alle Tests
pytest tests/ -v
```

### Frontend Tests (Vitest)

Die Frontend-Tests nutzen MSW (Mock Service Worker) zur API-Isolation.

```bash
cd frontend
# Alle Tests ausführen
npm test
# TDD-Mode (Watch)
npm run test:watch
```

### Test-Übersicht

| Bereich | Tool | Umfang |
| --- | --- | --- |
| **Backend** | pytest | API-Integration, LangGraph-Nodes, Security, Stripe-Webhooks |
| **Frontend** | Vitest | Component-Testing (MUI), API-Mocking (MSW), Case-Flow |

---

## 6. Dokumentation

| Dokument | Inhalt |
| --- | --- |
| [docs/VISION.md](docs/VISION.md) | Produktvision, MVP-Scope, Leitplanken |
| [docs/TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md) | Repo-Struktur, Stack, Dev-Workflow |
| [docs/API-DESIGN.md](docs/API-DESIGN.md) | API-Endpunkte (Spezifikation) |
| [docs/epics/](docs/epics/) | EPIC1–EPIC6 mit User Stories und Akzeptanzkriterien |
