# Issues Backlog – Resovva.ai

Übersicht der geplanten Aufgaben: Setup, Infrastruktur und User Stories (MVP).

---

## Inhaltsverzeichnis

1. [Setup & Infrastruktur](#1-setup--infrastruktur)
2. [User Stories (MVP)](#2-user-stories-mvp)

---

## 1. Setup & Infrastruktur

### [SETUP] Infrastructure Init

| Aspekt   | Beschreibung                                     |
| -------- | ------------------------------------------------ |
| **Ziel** | Projekt- und Infrastruktur-Grundgerüst aufsetzen |

**Tasks:**

- Init FastAPI Project mit Dockerfile
- Setup Qdrant (lokal/Docker)
- Setup Azure OpenAI Access

---

## 2. User Stories (MVP)

### [US-01] Document Ingestion Pipeline

| Feld      | Inhalt                                                                                 |
| --------- | -------------------------------------------------------------------------------------- |
| **Story** | Als System muss ich PDF- und EML-Dateien parsen können.                                |
| **Task**  | Implementiere `IngestionService`. Nutze `unstructured` oder PyPDF für Text-Extraktion. |
| **AC**    | Text wird sauber extrahiert, Metadaten (Dateiname) werden gespeichert.                 |

---

### [US-02] LLM Entity Extraction (LangChain)

| Feld      | Inhalt                                                                    |
| --------- | ------------------------------------------------------------------------- |
| **Story** | Das System extrahiert Zählernummer und Beträge automatisch.               |
| **Task**  | LangChain-Chain mit Pydantic Output Parser (`ExtractedEntity`) erstellen. |
| **AC**    | Test mit 3 anonymisierten Rechnungen erfolgreich.                         |

---

### [US-03] Chronology Builder Logic

| Feld      | Inhalt                                                                                                        |
| --------- | ------------------------------------------------------------------------------------------------------------- |
| **Story** | Das System ordnet Dokumente zeitlich.                                                                         |
| **Task**  | Das LLM muss aus dem Text das relevante Datum (z.B. Rechnungsdatum, nicht Druckdatum) erkennen und sortieren. |
| **AC**    | Liste von `ChronologyItem` wird korrekt nach Datum sortiert zurückgegeben.                                    |

---

### [US-04] Gap Analysis Agent

| Feld      | Inhalt                                                                          |
| --------- | ------------------------------------------------------------------------------- |
| **Story** | Das System erkennt fehlende Dokumente.                                          |
| **Task**  | Logik: Wenn Mahnung existiert, aber keine Rechnung davor → als Lücke markieren. |
| **AC**    | Rückgabe einer Liste von fehlenden Dokumenten/Fragen an den User.               |

---

### [US-05] PDF Dossier Generator

| Feld      | Inhalt                                                                                   |
| --------- | ---------------------------------------------------------------------------------------- |
| **Story** | Erstellung des finalen Reports.                                                          |
| **Task**  | Nutze ReportLab oder WeasyPrint. Template für Deckblatt + Chronologie-Tabelle erstellen. |
| **AC**    | PDF wird generiert und wirkt professionell.                                              |
