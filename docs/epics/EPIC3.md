# EPIC 3: AI Analysis & Extraction Engine

## 📋 Überblick

**Beschreibung:**
Dieses Epic implementiert den ersten Durchlauf des LangGraph-Agenten. Der maskierte Text aus Epic 2 wird vektorisiert (RAG) und in Qdrant gespeichert. Ein kosteneffizientes LLM (gpt-4o-mini) sucht gezielt nach Kern-Fakten (MaLo, Zählernummer, Beträge). Fehlen kritische Daten, pausiert der Agent (Early Exit) und bittet den Nutzer um Eingabe. Nach dem MaStR-Lookup präsentiert die UI die gefundenen Fakten zur manuellen Bestätigung (Human-in-the-Loop), bevor der Fall weiterläuft.

**Business Value:**

- Automatische Extraktion spart dem Nutzer manuelles Abtippen von Zählernummer, MaLo und Beträgen
- Kostendeckel unter 0,05 € pro Fall durch strikten Einsatz von gpt-4o-mini statt teurerer Modelle
- Human-in-the-Loop verhindert Fehler im Dossier durch KI-Halluzinationen – Nutzer hat volle Kontrolle

**Tech Notes:**

- **RAG:** LangChain `RecursiveCharacterTextSplitter` (~1000 Tokens/Chunk, 100 Overlap) + OpenAI `text-embedding-3-small` → Qdrant Collection `resovva_docs`
- **LLM:** Strikt `gpt-4o-mini` mit `with_structured_output(ExtractedEntity)` (Pydantic)
- **LangGraph State:** Persistiert via `langgraph-checkpoint-postgres`; Pausen via `interrupt_before` oder Conditional Edges

**Zeitschätzung:** ~55–65 Stunden

---

## 🎯 Tickets in diesem Epic

### US-3.1: RAG Foundation (Chunking & Embeddings)

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** Epic 2 (US-2.5 – maskierter Text liegt vor)
**Blocking:** US-3.2, US-3.4

**Beschreibung:**
Als Systembetreiber möchte ich große Dokumente in Vektoren umwandeln und in Qdrant speichern, damit die KI später effizient und kostengünstig nach spezifischen Informationen suchen kann.

**Akzeptanzkriterien:**

- [ ] Funktion teilt maskierten Rohtext in Chunks (max. 1000 Zeichen, 100 Zeichen Overlap)
- [ ] Chunks werden via OpenAI API (`text-embedding-3-small`) in Vektoren umgewandelt
- [ ] Vektoren werden mit Metadaten (`case_id`, `document_id`) in Qdrant-Collection `resovva_docs` gespeichert

**Implementierungs-Notizen:**

- Code-Path: `app/core/rag.py`, `app/infrastructure/qdrant_client.py`
- Komponenten: `langchain.text_splitter.RecursiveCharacterTextSplitter`, `openai` SDK, `qdrant-client`
- Collection-Schema: `{ vector: float[], payload: { case_id, document_id, chunk_index, text } }`
- Qdrant lokal via Docker: `qdrant/qdrant` Image in `docker-compose.yml`

---

### US-3.2: Core Entity Extraction (LLM)

**Status:** Backlog
**Aufwand:** 10 Stunden
**Assignee:** –
**Dependencies:** US-3.1
**Blocking:** US-3.3, US-3.5

**Beschreibung:**
Als Nutzer möchte ich, dass das System automatisch meine Zählernummer, Marktlokation (MaLo) und den Streitbetrag ausliest, damit ich diese nicht manuell abtippen muss.

**Akzeptanzkriterien:**

- [ ] LangGraph-Node `_node_extract` führt RAG-Suche in Qdrant nach relevanten Textstellen für Zähler, MaLo und Beträge aus
- [ ] Strikt `gpt-4o-mini` mit `with_structured_output(ExtractedEntity)` (kein Modell-Wechsel ohne Ticket)
- [ ] Ergebnis wird in `AgentState` geschrieben; nicht gefundene Felder werden mit `null` befüllt (kein Halluzinieren)

**Implementierungs-Notizen:**

- Code-Path: `app/agents/nodes/extract.py`, `app/agents/state.py`
- Pydantic-Modell `ExtractedEntity`: `meter_number: str | None`, `malo_id: str | None`, `dispute_amount: float | None`, `currency: str | None`
- RAG-Query: 3 separate Qdrant-Suchen mit zielgerichteten Queries (z.B. `"Zählernummer"`, `"Marktlokation MaLo"`, `"offener Betrag Forderung"`)
- Prompt explizit anweisen: bei Unsicherheit `null` zurückgeben, niemals raten

---

### US-3.3: Early Exit & Missing Data UI

**Status:** Backlog
**Aufwand:** 10 Stunden
**Assignee:** –
**Dependencies:** US-3.2
**Blocking:** US-3.4

**Beschreibung:**
Als Nutzer möchte ich sofort gewarnt werden, wenn essenzielle Daten (Zählernummer oder MaLo) fehlen, damit ich diese nachtragen kann, bevor das System Fehler macht.

**Akzeptanzkriterien:**

- [ ] Conditional Edge im LangGraph prüft nach Extraktion: Sind `meter_number` UND `malo_id` gleich `null`?
- [ ] Wenn ja: Agent-Status → `WAITING_FOR_USER`, LangGraph-Run pausiert (Interrupt)
- [ ] Frontend pollt Status und zeigt Meldung: „Wir konnten keine Zählernummer finden."
- [ ] UI bietet zwei Optionen: (1) manuelle Eingabe via Formular, (2) Button „Weiteres Dokument hochladen" (zurück zu Epic 2 Upload-Flow)

**Implementierungs-Notizen:**

- Code-Path: `app/agents/graph.py` (Conditional Edge), Frontend: `components/MissingDataForm.tsx`
- LangGraph: `interrupt_before=["_node_mastr_lookup"]` wenn Daten fehlen
- Manuell eingegebene Daten via POST `/api/v1/workflows/{case_id}/resume` → in `AgentState` schreiben
- Edge-Logik: `if state.meter_number is None and state.malo_id is None → "missing_data"` else `"mastr_lookup"`

---

### US-3.4: MaStR-API Lookup & AI Fallback

**Status:** Backlog
**Aufwand:** 10 Stunden
**Assignee:** –
**Dependencies:** US-3.1, US-3.3
**Blocking:** US-3.5

**Beschreibung:**
Als Nutzer möchte ich, dass das System meinen exakten Netzbetreiber anhand der MaLo identifiziert, da ich oft nur meinen Stromanbieter kenne.

**Akzeptanzkriterien:**

- [ ] Sobald valide MaLo vorliegt: Backend sendet HTTP-Request an offizielle MaStR-API (`mastr_lookup_tool`)
- [ ] Bei Erfolg: Netzbetreiber wird in `AgentState` gespeichert
- [ ] **Fallback:** API offline oder kein Ergebnis → RAG-Aufruf mit `gpt-4o-mini` extrahiert Netzbetreiber-Namen aus Briefkopf der Dokumente

**Implementierungs-Notizen:**

- Code-Path: `app/agents/nodes/mastr_lookup.py`, `app/agents/nodes/network_operator_fallback.py`
- MaStR-API: `https://www.marktstammdatenregister.de/MaStR/` (öffentliche REST-API, kein API-Key nötig)
- Timeout: 5 Sekunden; bei Timeout sofort Fallback triggern (kein Retry im MVP)
- Fallback-RAG-Query: `"Netzbetreiber Stadtwerke Verteilernetzbetreiber"` gegen Qdrant

---

### US-3.5: Human-in-the-Loop & Graph Resume

**Status:** Backlog
**Aufwand:** 12 Stunden
**Assignee:** –
**Dependencies:** US-3.2, US-3.4
**Blocking:** Epic 4 (Dossier-Generierung)

**Beschreibung:**
Als Nutzer möchte ich die von der KI erkannten Daten kontrollieren und korrigieren können, bevor das finale Dossier erstellt wird.

**Akzeptanzkriterien:**

- [ ] Nach Extraktion und MaStR-Lookup: Agent-Status → `WAITING_FOR_USER` (Interrupt)
- [ ] Frontend zeigt Formular mit extrahierten Daten: Zählernummer, MaLo, Betrag, Netzbetreiber
- [ ] Nutzer kann alle Felder editieren oder direkt „Bestätigen & Weiter" klicken
- [ ] Klick sendet POST `/api/v1/workflows/resume` mit den finalen, bestätigten Daten
- [ ] LangGraph überschreibt internen State mit User-Daten und weckt Agenten auf (→ Epic 4)

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/workflows.py` (POST /resume), Frontend: `components/ConfirmationForm.tsx`
- LangGraph Resume: `graph.update_state(thread_id, user_confirmed_data)` + `graph.invoke(None, config)`
- State-Felder die überschrieben werden: `meter_number`, `malo_id`, `dispute_amount`, `network_operator`
- UI: Änderungsfelder grün hervorheben wenn abweichend vom KI-Vorschlag (Transparenz)

---

## ✅ Definition of Done (für alle Tickets)

- [ ] Code geschrieben (Backend + Frontend)
- [ ] Tests schreiben (Unit + Integration)
- [ ] Code Review bestanden (≥2 Approvals)
- [ ] Linting: 0 Errors
- [ ] Test Coverage: ≥80%
- [ ] Dokumentation aktualisiert (JSDoc/Docstrings)
- [ ] Security Review durchgeführt
- [ ] Performance-Tests bestanden
- [ ] Git-Commit mit aussagekräftiger Nachricht
- [ ] Changelog aktualisiert

---

## 🔗 Abhängigkeiten & Blockierung

```
US-3.1 (RAG Foundation)
├─ Abhängig von: Epic 2 – US-2.5 (maskierter Text)
├─ Blocking für: US-3.2, US-3.4

US-3.2 (Core Entity Extraction)
├─ Abhängig von: US-3.1
├─ Blocking für: US-3.3, US-3.5

US-3.3 (Early Exit & Missing Data UI)
├─ Abhängig von: US-3.2
├─ Blocking für: US-3.4

US-3.4 (MaStR-API Lookup & Fallback)
├─ Abhängig von: US-3.1, US-3.3
├─ Blocking für: US-3.5

US-3.5 (Human-in-the-Loop & Resume)
├─ Abhängig von: US-3.2, US-3.4
├─ Blocking für: Epic 4 (Dossier-Generierung)
```
