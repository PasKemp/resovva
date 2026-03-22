# Resovva.de

**Projekt-Spezifikation** – Intelligenter Fall-Assistent (LegalTech).

---

## Inhaltsverzeichnis

1. [Executive Summary](#1-executive-summary)
2. [Technisches Anforderungsprofil](#2-technisches-anforderungsprofil-context-for-dev-ai)
3. [Kern-Workflow: „Der Rote Faden“](#3-kern-workflow-der-rote-faden)
4. [Lokale Entwicklung (.venv)](#4-lokale-entwicklung-venv)
5. [Dokumentation](#5-dokumentation)

---

## 1. Executive Summary

Resovva.de ist ein **KI-gestützter LegalTech-Service**, der Endverbrauchern hilft, komplexe Streitigkeiten mit Stromanbietern und Netzbetreibern (z.B. Abrechnungsfehler, PV-Probleme, Anbieterwechsel) effizient zu lösen. Das System fungiert als intelligenter Fall-Assistent, der Dokumente analysiert, eine Chronologie erstellt und ein professionelles Beschwerde-Dossier für Behörden oder Schlichtungsstellen generiert.

| Aspekt          | Beschreibung                                                                                         |
| --------------- | ---------------------------------------------------------------------------------------------------- |
| **Preismodell** | 20€ pro Fall (Pay-per-Case).                                                                         |
| **USP**         | Automatisierte Fallaufbereitung („Der Rote Faden“) und Identifikation der richtigen Zuständigkeiten. |

---

## 2. Technisches Anforderungsprofil (Context for Dev-AI)

Kontext: Senior Software-Entwickler (7+ Jahre Erfahrung). Geplanter Stack:

### Backend

- **Python 3.12+** mit **FastAPI**.

### KI-Orchestrierung

- **LangChain** oder **LangGraph** (für stateful, zyklische Agenten-Workflows).

### RAG-Komponenten

| Komponente     | Technologie                                                   |
| -------------- | ------------------------------------------------------------- |
| **Embeddings** | OpenAI `text-embedding-3-small` (oder lokal via HuggingFace). |
| **Vektor-DB**  | Qdrant (Deployment im K8s-Cluster).                           |
| **LLM**        | GPT-4o (via Azure Germany für DSGVO-Konformität).             |

### Infrastructure & DevOps

- **Containerisierung:** Docker.
- **Orchestrierung:** Kubernetes (K8s).
- **CI/CD:** Jenkins (automatisierte Build- & Deployment-Pipelines).

### Datenschutz

- **Privacy-by-Design.** PII-Masking vor LLM-Transfer, automatisches Löschen der Daten **30 Tage nach Fallabschluss**.

---

## 3. Kern-Workflow: „Der Rote Faden“

Der Agent führt folgende Schritte autonom oder semi-autonom durch:

| Schritt                     | Beschreibung                                                                                                                                                                                               |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Ingestion & Parsing**  | Extraktion von Daten aus PDFs (Rechnungen, Verträge) und E-Mails.                                                                                                                                          |
| **2. Entitäten-Extraktion** | Identifikation von Zählernummern, Marktlokationen (MaLo), Daten und Beträgen.                                                                                                                              |
| **3. Chronologie-Modul**    | Erstellung eines zeitlichen Ablaufs der Korrespondenz und Ereignisse.                                                                                                                                      |
| **4. Gap-Analysis**         | Der Agent erkennt fehlende Informationen (z.B. „Einspruchsschreiben vom 15.02. fehlt“) und bittet den User um Ergänzung.                                                                                   |
| **5. Jurisdiction-Finder**  | Abgleich mit der **MaStR-API** (Marktstammdatenregister), um den exakten Netzbetreiber zu finden.                                                                                                          |
| **6. Dossier-Generation**   | Erstellung eines strukturierten PDF-Dossiers inklusive: Sachverhaltsdarstellung, chronologische Beweismittel-Auflistung, konkrete Forderung (basierend auf hinterlegten AGB-Standards/Gesetzes-Templates). |

---

## 4. Lokale Entwicklung

### Voraussetzungen

- **Docker Desktop** (für Infrastruktur und optionalen Full-Stack-Betrieb)
- **Python 3.12+** und **Node.js 20+** (für lokale Backend-/Frontend-Entwicklung)

---

### Option A: Kompletter Stack via Docker Compose

Startet alle Dienste (Postgres, MinIO, Qdrant, Backend, Frontend) in einem Schritt:

```bash
docker-compose up --build
```

Tabellen werden beim ersten Backend-Start automatisch erstellt.

---

### Option B: Nur Infrastruktur via Docker + Backend lokal (empfohlen für Entwicklung)

**Schritt 1** – Infrastruktur-Dienste starten (Postgres, MinIO, Qdrant — Tabellen werden beim ersten Backend-Start automatisch erstellt):

```bash
docker-compose up postgres minio qdrant
```

**Schritt 2** – Backend-Umgebung einrichten:

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate        # Windows: ..\.venv\Scripts\activate
pip install -e ".[dev,postgres]"
```

**Schritt 3** – `.env`-Datei anlegen:

```bash
cp .env.example .env
```

Die `.env` enthält bereits alle lokalen Defaults. Wichtig: `OPENAI_API_KEY` eintragen.

**Schritt 4** – Backend starten:

```bash
uvicorn app.main:app --reload
```

**Schritt 6** – Frontend starten (separates Terminal):

```bash
cd ../frontend
npm install
npm run dev
```

---

### Dienste & URLs

| Dienst | URL | Zugangsdaten |
|---|---|---|
| **Frontend** | http://localhost:5173 | – |
| **Backend API** | http://localhost:8000 | – |
| **Swagger / API-Docs** | http://localhost:8000/docs | – |
| **PostgreSQL** | localhost:5432 | `resovva` / `password` |
| **MinIO Console** | http://localhost:9001 | `minioadmin` / `minioadmin` |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | – |

---

### Tests

Alle Tests:

```bash
cd backend
pytest tests/ -v
```

Einzelnen Test ausführen:

```bash
pytest tests/test_api.py::test_health -v
```

Nur Tests für ein Modul:

```bash
pytest tests/test_auth.py -v
```

---

### Linting

```bash
cd backend
ruff check app
```


---

## 5. Dokumentation

| Dokument                                                          | Inhalt                                           |
| ----------------------------------------------------------------- | ------------------------------------------------ |
| [00_VISION.md](docs/00_VISION.md)                                 | Produktvision, MVP-Scope, technische Leitplanken |
| [01_TECHNICAL_ARCHITECTURE.md](docs/01_TECHNICAL_ARCHITECTURE.md) | Repo-Struktur, Stack, Dev-Workflow               |
| [API-DESIGN.md](docs/API-DESIGN.md)                               | API-Oberfläche / Endpunkte (Entwurf)             |
| [epics/](docs/epics/)                                             | Epics EPIC1–EPIC6                                |

Hinweis: Ältere oder ausgelagerte Docs (z. B. User Flow, Data Schema, Backlog) können bei Bedarf wieder unter `docs/` ergänzt und hier verlinkt werden.
