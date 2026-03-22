# EPIC 4: "Der Rote Faden" (Chronology & Gap Analysis)

## 📋 Überblick

**Beschreibung:**
Dieses Epic transformiert unstrukturierte Falldaten in eine präzise, juristisch verwertbare Chronologie. Ein Map-Reduce-Verfahren mit LLMs extrahiert Ereignisse aus jedem Dokument (Map) und aggregiert sie zu einer dedizierten Gesamt-Timeline mit Lückenerkennung (Reduce). Der Nutzer hat volle Kontrolle: Bearbeiten, Löschen, eigene Ereignisse hinzufügen und fehlende Dokumente iterativ nachreichen – ohne dass Nutzer-Änderungen je überschrieben werden.

**Business Value:**

- Automatische Chronologie spart dem Nutzer stundenlange manuelle Rekonstruktion des Streitfalls
- Gap Analysis weist proaktiv auf fehlende Belege hin – stärkt die Beweismittellage vor Einreichung
- Iterativer Upload-Loop ermöglicht schrittweise Vervollständigung ohne Datenverlust

**Tech Notes:**

- **Map:** `gpt-4o-mini` pro Dokument → lokale Event-Extraktion (günstig, parallelisierbar)
- **Reduce:** `gpt-4o` für Aggregation, Deduplizierung und Gap-Erkennung (einmaliger teurer Call)
- **State Management:** `PostgresSaver` (LangGraph Checkpointer) persistiert Timeline; `source: user`-Flag schützt manuelle Einträge vor KI-Überschreibung
- **Wording:** Keine Amtssprache – „Beleg fehlt", „Eigene Angabe" statt juristischer Fachbegriffe

**Zeitschätzung:** ~55–65 Stunden

---

## 🎯 Tickets in diesem Epic

### US-4.1: Event-Extraktion pro Dokument (Map-Phase)

**Status:** Backlog
**Aufwand:** 10 Stunden
**Assignee:** –
**Dependencies:** Epic 3 – US-3.5 (bestätigter AgentState liegt vor)
**Blocking:** US-4.2

**Beschreibung:**
Als Systembetreiber möchte ich jedes Dokument einzeln auf Ereignisse scannen, um eine saubere Datenbasis für die Chronologie zu schaffen, ohne teure LLMs zu verschwenden.

**Akzeptanzkriterien:**

- [ ] Neuer LangGraph-Node `_node_extract_events` verarbeitet jedes hochgeladene Dokument einzeln
- [ ] Node nutzt `gpt-4o-mini` mit `with_structured_output(List[ChronologyEvent])` (Pydantic)
- [ ] KI extrahiert sowohl das Erstellungsdatum des Dokuments als auch referenzierte Ereignisse (z.B. „Wie am 12.04. besprochen")
- [ ] Extrahierte Event-Listen werden als Zwischenschritt im `AgentState` gespeichert

**Implementierungs-Notizen:**

- Code-Path: `app/agents/nodes/extract_events.py`, `app/agents/state.py`
- Pydantic-Modell `ChronologyEvent`: `date: date | None`, `description: str`, `source_document_id: str`, `source: Literal["ai", "user"]`
- Dokumente parallel verarbeiten via `asyncio.gather()` um Latenz zu minimieren
- Prompt: explizit anweisen, referenzierte Ereignisse (`"am X wurde telefoniert"`) als eigenständige Events zu extrahieren

---

### US-4.2: Master-Chronologie & Gap Analysis (Reduce-Phase)

**Status:** Backlog
**Aufwand:** 12 Stunden
**Assignee:** –
**Dependencies:** US-4.1
**Blocking:** US-4.3, US-4.5

**Beschreibung:**
Als Nutzer möchte ich, dass das System alle meine Dokumente in eine logische, chronologische Reihenfolge bringt und mich auf fehlende Unterlagen hinweist.

**Akzeptanzkriterien:**

- [ ] LangGraph-Node `_node_build_master_timeline` nimmt alle Event-Listen aus US-4.1 und übergibt sie an `gpt-4o`
- [ ] KI dedupliziert überschneidende Ereignisse und sortiert chronologisch (ältester Eintrag zuerst)
- [ ] **Gap Analysis:** KI prüft auf logische Brüche (z.B. Mahnung verweist auf Rechnung die nicht existiert)
- [ ] Erkannte Lücken werden als spezielle Einträge eingefügt: `is_gap: true`, Beschreibung: „Vermutlich fehlendes Dokument: Rechnung vom 01.03."

**Implementierungs-Notizen:**

- Code-Path: `app/agents/nodes/build_master_timeline.py`
- Modell: `gpt-4o` (kein Mini – Reduce-Phase braucht höhere Reasoning-Qualität für Deduplizierung)
- Prompt-Instruktion: Events mit `source: user` sind unveränderlich – niemals anpassen, löschen oder zusammenführen
- Gap-Typen die erkannt werden sollen: fehlende Rechnung vor Mahnung, fehlende Mahnung vor Inkasso, fehlende Kündigung vor Neuvertrag
- Master-Timeline in DB persistieren: `cases.timeline` (JSONB-Feld)

---

### US-4.3: UI – Der interaktive „Rote Faden"

**Status:** Backlog
**Aufwand:** 14 Stunden
**Assignee:** –
**Dependencies:** US-4.2
**Blocking:** US-4.4, US-4.5

**Beschreibung:**
Als Nutzer möchte ich die von der KI erstellte Chronologie sehen, prüfen und bearbeiten können, da nur ich die volle Wahrheit über meinen Fall kenne.

**Akzeptanzkriterien:**

- [ ] Frontend pollt Status und zeigt bei Abschluss die Chronologie als visuelle Zeitstrahl-Komponente oder Tabelle an
- [ ] Jeder KI-generierte Eintrag hat Kontextmenü (Drei-Punkte) mit Optionen „Bearbeiten" und „Löschen"
- [ ] Änderungen senden PUT `/api/v1/cases/{case_id}/timeline` → Graph-State aktualisiert, Event als `source: user` markiert
- [ ] Lücken (Gaps) werden visuell hervorgehoben: gelbes Warn-Icon mit Text „Hier fehlt uns ein Beleg. Du kannst ihn nachreichen oder ignorieren."

**Implementierungs-Notizen:**

- Code-Path: Frontend: `components/Timeline.tsx`, `app/api/routes/timeline.py` (PUT /timeline)
- UI-Komponente: chronologische Liste mit Datum links, Beschreibung rechts, Icon für Typ (Dokument / Telefonat / Gap)
- `source: user`-Events: visuell mit Badge „Eigene Angabe" kennzeichnen
- Gap-Einträge: gelber Hintergrund, kein Kontextmenü „Löschen" (nur „Ignorieren" + „Dokument hochladen")
- API: PATCH-Semantik – nur geänderte Felder senden, nicht gesamte Timeline

---

### US-4.4: UI – Manuelle Ereignisse hinzufügen (ohne Beleg)

**Status:** Backlog
**Aufwand:** 6 Stunden
**Assignee:** –
**Dependencies:** US-4.3
**Blocking:** –

**Beschreibung:**
Als Nutzer möchte ich wichtige Ereignisse (z.B. Telefonate, Haustürgespräche) manuell in die Chronologie eintragen können, auch wenn ich kein Papierdokument dafür habe.

**Akzeptanzkriterien:**

- [ ] Chronologie-UI bietet Button „Ereignis hinzufügen"
- [ ] Modal öffnet sich mit Pflichtfeldern: Datum (Datepicker) und Beschreibung (Freitext)
- [ ] Nach Speichern wird Ereignis chronologisch korrekt in die Ansicht einsortiert
- [ ] Event wird im State als `source: user` + Label „Eigene Angabe (ohne Beleg)" gespeichert – sichtbar im finalen Dossier

**Implementierungs-Notizen:**

- Code-Path: Frontend: `components/AddEventModal.tsx`, API: POST `/api/v1/cases/{case_id}/timeline`
- Datepicker: keine Zukunftsdaten erlauben (Datum muss ≤ heute sein)
- Beschreibung: max. 500 Zeichen, Pflichtfeld
- Chronologische Einsortierung im Frontend nach Datum (kein Re-Render der gesamten Liste nötig, lokales State-Update)

---

### US-4.5: Die „Zurück-Schleife" (Iterativer Upload)

**Status:** Backlog
**Aufwand:** 14 Stunden
**Assignee:** –
**Dependencies:** US-4.2, US-4.3
**Blocking:** Epic 5 (Dossier-Generierung)

**Beschreibung:**
Als Nutzer möchte ich, wenn das System mich auf eine Lücke hinweist, das fehlende Dokument hochladen können, woraufhin sich die Chronologie automatisch aktualisiert.

**Akzeptanzkriterien:**

- [ ] Gap-Einträge in der UI bieten Button „Fehlendes Dokument hochladen"
- [ ] Klick öffnet Upload-Flow aus Epic 2 (inkl. QR-Code-Option)
- [ ] Nach OCR & Masking wird LangGraph-Agent an richtiger Stelle aufgeweckt (resume)
- [ ] Agent führt Map-Reduce-Pipeline (US-4.1 + US-4.2) **nur für das neue Dokument** aus und webt Erkenntnisse in die bestehende Master-Timeline ein
- [ ] **Kritisch:** Events mit `source: user` werden durch den Re-Run unter keinen Umständen überschrieben, gelöscht oder zusammengeführt

**Implementierungs-Notizen:**

- Code-Path: `app/agents/nodes/incremental_update.py`, Frontend: Wiederverwendung der Upload-Komponenten aus Epic 2
- Resume-Punkt: `graph.update_state()` mit neuem Dokument-Context + Bestehender Timeline
- Prompt für Reduce-Re-Run: `"Die folgende Timeline ist bereits bestätigt. Füge nur neue, nicht bereits vorhandene Ereignisse hinzu. Events mit source=user sind UNVERÄNDERLICH."`
- Merge-Strategie: neues Event wird eingefügt wenn `date + description` nicht auf existierendes Event matchen (simple Duplikat-Erkennung)

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
US-4.1 (Event-Extraktion / Map)
├─ Abhängig von: Epic 3 – US-3.5 (bestätigter AgentState)
├─ Blocking für: US-4.2

US-4.2 (Master-Chronologie & Gap Analysis / Reduce)
├─ Abhängig von: US-4.1
├─ Blocking für: US-4.3, US-4.5

US-4.3 (Interaktive Timeline UI)
├─ Abhängig von: US-4.2
├─ Blocking für: US-4.4, US-4.5

US-4.4 (Manuelle Ereignisse hinzufügen)
├─ Abhängig von: US-4.3
├─ Blocking für: –

US-4.5 (Iterativer Upload / Zurück-Schleife)
├─ Abhängig von: US-4.2, US-4.3
├─ Blocking für: Epic 5 (Dossier-Generierung)
```
