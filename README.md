# Resovva.ai

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

Resovva.ai ist ein **KI-gestützter LegalTech-Service**, der Endverbrauchern hilft, komplexe Streitigkeiten mit Stromanbietern und Netzbetreibern (z.B. Abrechnungsfehler, PV-Probleme, Anbieterwechsel) effizient zu lösen. Das System fungiert als intelligenter Fall-Assistent, der Dokumente analysiert, eine Chronologie erstellt und ein professionelles Beschwerde-Dossier für Behörden oder Schlichtungsstellen generiert.

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

## 4. Lokale Entwicklung (.venv)

Das Projekt nutzt eine virtuelle Umgebung im Ordner `.venv`:

```powershell
# Venv anlegen (einmalig)
python -m venv .venv

# Aktivieren (PowerShell)
.\.venv\Scripts\Activate.ps1

# Abhängigkeiten inkl. Dev-Tools installieren
pip install -e ".[dev]"
```

Danach: `uvicorn app.main:app --reload`, `pytest tests/ -v`, `ruff check app`.

---

## 5. Dokumentation

| Dokument                                          | Inhalt                                           |
| ------------------------------------------------- | ------------------------------------------------ |
| [00_PRODUCT_VISION.md](docs/00_PRODUCT_VISION.md) | Produktvision, MVP-Scope, technische Leitplanken |
| [01_USER_FLOW.md](docs/01_USER_FLOW.md)           | User Flow & System States (Mermaid-Diagramm)     |
| [02_DATA_SCHEMA.md](docs/02_DATA_SCHEMA.md)       | Data Schema & Domain Models (Pydantic)           |
| [issues_backlog.md](docs/issues_backlog.md)       | Setup-Tasks und User Stories (Backlog)           |
