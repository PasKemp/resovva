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
|---|---|
| **1. Ingestion** | PDF-Upload → Textextraktion (pypdf → Azure Fallback) |
| **2. PII-Masking** | IBAN, E-Mail vor LLM-Transfer schwärzen |
| **3. Entitäten-Extraktion** | MaLo-ID, Zählernummer, Beträge, Daten per GPT-4o |
| **4. Chronologie** | Zeitlicher Ablauf aus allen Dokumenten |
| **5. Gap-Analysis** | Fehlende Belege identifizieren, Nutzer um Ergänzung bitten |
| **6. Dossier** | Strukturiertes PDF-Dossier für Schlichtungsstellen |

---

## 2. Implementierungsstand

| Epic | Beschreibung | Status |
|---|---|---|
| **Epic 1** | Auth, Sessions, Multi-Case-Dashboard, DSGVO Hard-Delete | ✅ Vollständig |
| **Epic 2** | Dokument-Upload, OCR, PII-Masking, QR-Code-Upload | ✅ Vollständig |
| **Epic 3** | LangGraph-Agent, RAG, Entitäten-Extraktion, MaStR-Lookup, HiTL | ✅ Vollständig (US-3.3 Frontend partiell) |
| **Epic 4** | Gap-Analysis, Nutzer-Feedback-Loop | 📋 Backlog |
| **Epic 5** | Stripe-Zahlung (Pay-per-Case) | 📋 Backlog |
| **Epic 6** | PDF-Dossier-Generierung | 📋 Backlog |

---

## 3. Stack

### Backend

- **Python 3.12+** · **FastAPI** · **SQLAlchemy** · **PostgreSQL 15**
- **LangGraph** – stateful KI-Agent (Knoten: ingest → extract → chronology → gaps)
- **GPT-4o** – Azure OpenAI (Produktion, DSGVO) · Standard OpenAI (Entwicklung)
- **Qdrant** – Vektordatenbank für Dokument-Embeddings
- **MinIO** – S3-kompatibler Objektspeicher (lokal); AWS S3 / Azure Blob (Produktion)

### Frontend

- **React 18** · **TypeScript** · **Vite** · **Material-UI**

### DevOps

- **Docker Compose** – lokale Entwicklungsumgebung
- **Kubernetes** – Produktions-Deployment (`k8s/`)
- **GitHub Actions** – CI/CD (pytest → Docker Build → Push zu GHCR)

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
|---|---|---|
| **Frontend** | <http://localhost:5173> | – |
| **Backend API** | <http://localhost:8000> | – |
| **Swagger / Docs** | <http://localhost:8000/docs> | – |
| **PostgreSQL** | localhost:5432 | `resovva` / `password` |
| **MinIO S3 API** | <http://localhost:9000> | `minioadmin` / `minioadmin` |
| **MinIO Console** | <http://localhost:9001> | `minioadmin` / `minioadmin` |
| **Qdrant Dashboard** | <http://localhost:6333/dashboard> | – |

---

## 5. Tests

Voraussetzung: PostgreSQL läuft (via Docker Compose). Die Test-DB `resovva_test` wird automatisch angelegt.

```bash
cd backend

# Alle Tests
pytest tests/ -v

# Nur ein Modul
pytest tests/test_auth.py -v

# Einzelner Test
pytest tests/test_auth.py::test_login_success -v
```

### Test-Struktur

| Datei | Inhalt | Tests |
|---|---|---|
| `test_security.py` | `hash_password`, JWT, Reset-Token, PII-Masking | 25 |
| `test_auth.py` | Register, Login, Logout, `/me`, Passwort-Reset | 25 |
| `test_cases.py` | Dashboard, Tenant-Isolation, DSGVO Hard-Delete | 15 |
| `test_api.py` | Health-Check | 1 |

Ohne laufendes PostgreSQL werden DB-Tests automatisch übersprungen (`SKIPPED`), Security-Unit-Tests laufen weiterhin durch.

Eigene Test-DB-URL setzen:

```bash
TEST_DATABASE_URL=postgresql://user:pass@host:5432/mydb pytest tests/ -v
```

### Linting

```bash
cd backend
ruff check app
```

---

## 6. Dokumentation

| Dokument | Inhalt |
|---|---|
| [docs/00_VISION.md](docs/00_VISION.md) | Produktvision, MVP-Scope, Leitplanken |
| [docs/01_TECHNICAL_ARCHITECTURE.md](docs/01_TECHNICAL_ARCHITECTURE.md) | Repo-Struktur, Stack, Dev-Workflow |
| [docs/02_API-DESIGN.md](docs/02_API-DESIGN.md) | API-Endpunkte (Spezifikation) |
| [docs/epics/](docs/epics/) | EPIC1–EPIC6 mit User Stories und Akzeptanzkriterien |
