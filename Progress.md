# Progress.md – Resovva.de

Stand: 2026-03-26

---

## Gesamtstatus: EPIC 1 ✅ · EPIC 2 ✅ · EPIC 3 ✅ · EPIC 4 ✅ · EPIC 5 ✅

---

## EPIC 5: Checkout & Monetization (Die Paywall) ✅

### US-5.1: Stripe Checkout Session ✅

- `api/v1/checkout.py` → `POST /cases/{case_id}/checkout`
- Dev-Modus (kein `STRIPE_SECRET_KEY`): Fall direkt auf `PAID`, `checkout_url = ""`
- Prod-Modus: `stripe.checkout.Session.create()` mit `allow_promotion_codes=True`, `client_reference_id=user_id`, `metadata={case_id}`
- `cancel_url` → `/dashboard?payment=cancelled&case_id={id}`, `success_url` → `/dashboard?payment=success`
- Fall-Status → `PAYMENT_PENDING`, `stripe_session_id` in DB persistiert

### US-5.2: Webhook-Handler ✅

- `POST /api/v1/webhooks/stripe`: Signaturprüfung via `stripe.Webhook.construct_event()` (→ 400 bei Fehler)
- `checkout.session.completed` → Fall-Status auf `PAID`; Idempotenz: bereits `PAID` wird übersprungen
- Bonus: `payment_intent` in `case.extracted_data["stripe_payment_intent"]` persistiert (Buchhaltungs-Trail)

### US-5.3: Paywall UI ✅

- `features/case/steps/CheckoutStep.tsx`: Leistungsübersicht, Preis-Box (20,00 €), gesetzlich vorgeschriebener Widerrufs-Verzicht-Text
- Checkbox **nicht** vorausgefüllt; Button deaktiviert bis Zustimmung erteilt

### US-5.4: Abgebrochene Zahlungen & Retry ✅

- `Dashboard.tsx`: `STATUS_CTA["Zahlung ausstehend"] = "Zahlung abschließen"`, `STATUS_STEP[...] = 3` → CaseFlow öffnet direkt auf Checkout-Step
- `paymentToast` via `useEffect` liest `?payment=cancelled` aus URL, zeigt 6s-Toast, bereinigt URL via `window.history.replaceState`
- `App.tsx` → `openCase(caseId?, step?)` trägt optionalen `step` weiter
- `types/index.ts`: `PAYMENT_PENDING` in `CaseStatusApi` + `STATUS_MAP`

### US-5.5: Automatisierte Rechnungsstellung ✅ (Konfiguration)

- Kein Code – reine Stripe-Dashboard-Konfiguration: Steuer-Setup (19 % MwSt.), Rechnungsmail-Template, Stripe Branding

---

## EPIC 4: "Der Rote Faden" – Chronologie & Gap-Analysis ✅

### US-4.1: Event-Extraktion pro Dokument (Map-Phase) ✅

- `agents/nodes/extract_events.py` → `node_extract_events()`: `gpt-4o-mini` mit `ChronologyEventExtracted` Pydantic-Modell
- Parallele Verarbeitung via `asyncio.gather()`, max. 6000 Zeichen pro Dokument
- Erkennt Dokumentdatum + referenzierte Daten (z. B. „am 12.04. besprochen")
- Fall-Status → `BUILDING_TIMELINE`, Ergebnisse in `state["events_per_doc"]`

### US-4.2: Master-Chronologie & Gap-Analysis (Reduce-Phase) ✅

- `agents/nodes/build_master_timeline.py` → `node_build_master_timeline()`: `gpt-4o` für Reduce
- Deduplizierung, Gap-Erkennung (max. 5 Gaps), Schutz von `source_type='user'`-Ereignissen
- Fall-Status → `TIMELINE_READY`; Persistierung in DB via `_persist_timeline()`

### US-4.3: UI – Interaktiver "Roter Faden" ✅

- `api/v1/timeline.py`: `GET`, `PATCH`, `DELETE /cases/{case_id}/timeline/{event_id}`
- `features/case/steps/TimelineStep.tsx`: Polling (2 s), `TimelineRow` mit 3-Punkte-Menü (Bearbeiten/Löschen), `GapRow` gelb hinterlegt mit „Nachreichen"-Button
- Source-Badges: „KI-Extraktion" (blau) vs. „Eigene Angabe" (lila)

### US-4.4: Manuelle Ereignisse hinzufügen ✅

- `POST /cases/{case_id}/timeline`: `source_type='user'`, Datum-Validierung (kein Zukunftsdatum)
- `components/AddEventModal.tsx`: Datums-Picker (max=heute), Beschreibungs-Textarea (500 Zeichen), Auto-Sortierung

### US-4.5: Die "Zurück-Schleife" (Iterativer Upload) ✅

- `agents/nodes/incremental_update.py` → `run_incremental_update(case_id, doc_id)`: neues Dokument extrahieren → KI-Ereignisse löschen → Merge via `gpt-4o` mit `[USER]`-Markierung
- `POST /cases/{case_id}/timeline/refresh?document_id={id}`: setzt `BUILDING_TIMELINE`, startet `BackgroundTask`, antwortet mit 202

---

## EPIC 3: AI Analysis & Extraction Engine ✅

### US-3.1: RAG Foundation ✅

- `core/rag.py`: `chunk_and_embed()`, `search_rag()`, `search_rag_with_meta()` — Chunking (1000 Zeichen, 100 Overlap), OpenAI `text-embedding-3-small`, Qdrant-Speicherung
- `infrastructure/qdrant_client.py`: Collection-Management (1536-dim), Upsert, semantische Suche mit `case_id`-Filter, DSGVO-Delete

### US-3.2: Core Entity Extraction ✅

- `agents/nodes/extract.py`: 3 gezielte RAG-Suchen (Zählernummer, MaLo, Betrag), strikt `gpt-4o-mini` mit `with_structured_output`
- Confidence-Scoring: Regex-Match 1.0 · LLM-only 0.6 · fehlend 0.0
- Source-Tracking: `source_document_id` + `source_text_snippet` pro Feld

### US-3.3: Early Exit & Missing Data UI ✅

- `agents/graph.py`: Conditional Edge `should_request_more_data()` — wenn `meter_number IS NULL AND malo_id IS NULL` → Pause
- Case-Status → `WAITING_FOR_USER`; LangGraph-Interrupt vor `confirm`-Node
- Frontend: `AnalysisStep` zeigt im Review-Zustand bei fehlenden Schlüsselfeldern Warnbox mit **„Weiteres Dokument hochladen"**-Button (US-3.3 vollständig)

### US-3.4: MaStR-API Lookup & AI Fallback ✅

- `agents/nodes/mastr_lookup.py`: Echter MaStR-API-Call mit 5-Sek-Timeout
- RAG-Fallback bei API-Ausfall; Persistierung in DB mit Confidence-Score

### US-3.5: Human-in-the-Loop & Graph Resume ✅

- `api/v1/cases.py` → `PUT /cases/{case_id}/analysis/confirm`: HiTL-Bestätigung mit `graph.update_state()` + `graph.invoke(None, config)` Resume
- `GET /cases/{case_id}/extraction-result`: Confidence-Scores + needs_review-Flags (US-9.2)
- Frontend `AnalysisStep`: vollständiges Review-Formular, Bestätigen-Button → nächster Step

### Bonus: Über EPIC 3 hinaus implementiert

- `agents/nodes/detect_opponent.py`: Streitpartei-Erkennung mit Kategorie-Klassifikation (US-9.1)
- `core/category_field_config.py`: Kategorie-Feld-Mapping für dynamische Formularfelder (US-9.5)
- `api/v1/cases.py` → `PATCH /cases/{case_id}`: Opponent-Kategorie/-Name updaten (US-9.4)
- `api/v1/documents.py`: S3/MinIO-Upload mit Magic-Byte-Validierung + Async-OCR (EPIC 2 Abschluss)
- `domain/models/db.py`: `MobileUploadToken`, `LlamaParseUsage` — EPIC 2 Erweiterungen

---

## EPIC 2: Dokument-Upload & OCR ✅

### US-2.6: Masking Preview & Vertrauensaufbau ✅

- `features/case/steps/AnalysisStep.tsx` `DocContent`: Masking-Tokens (`***IBAN***`, `***@***.***`) werden in `__MASK_IBAN__` / `__MASK_EMAIL__`-Platzhalter umgewandelt
- Benutzerdefinierter `code`-Renderer in `MD_COMPONENTS` erkennt Platzhalter und rendert grün hinterlegte `<span>`-Elemente mit Tooltip „Zu deiner Sicherheit vor der KI verborgen"
- Bestehende Datenschutz-Hinweisbox + grünes Highlighting erfüllen US-2.6 vollständig

### Weitere US-2.x ✅

- S3/MinIO-Upload (10 MB-Limit, MIME-Validierung), Async-OCR-Pipeline
- PII-Masking (IBAN, E-Mail) vor LLM-Übergabe (`core/security.py`)
- QR-Code Mobile-Upload (`MobileUploadToken`, `POST /mobile-upload`)
- LlamaParse-Fallback für schwierige PDFs + Free-Tier-Monitoring

---

## EPIC 1: User Onboarding & Session Management ✅

### US-1.1: DB-Schema & Security Foundation ✅

- `domain/models/db.py`: Tabellen `users`, `cases`, `documents`, `chronology_events`, `password_reset_tokens`
- `core/security.py`: `hash_password`, `verify_password` (bcrypt), `create_access_token`, `decode_access_token` (JWT HS256), `generate_reset_token`, `hash_reset_token`
- `infrastructure/database.py` (neu): Lazy-Singleton Engine, `get_db()` FastAPI-Dependency
- `alembic/` (neu): Vollständiges Alembic-Setup mit initialer Migration `001_initial_schema.py`
- `pyproject.toml`: passlib[bcrypt], python-jose[cryptography], slowapi, resend, alembic hinzugefügt

### US-1.2: Registrierung ✅

- `POST /api/v1/auth/register` – E-Mail-Validierung, Passwort ≥8 Zeichen, bcrypt-Hash, Set-Cookie

### US-1.3: Login & Session ✅

- `POST /api/v1/auth/login` – Passwort-Verify, JWT generieren, HttpOnly-Cookie
- Rate-Limiting: 5 Versuche / 15 Minuten / IP (slowapi)
- Neutrale Fehlermeldung (kein Account-Enumeration-Leak)

### US-1.4: API-Security & Tenant Isolation ✅

- `api/dependencies.py`: `get_current_user` – JWT aus Cookie → User-Lookup
- `CurrentUser = Annotated[User, Depends(get_current_user)]` als typisierter Alias
- Cases: Fremde `case_id` → 404 (nicht 403)

### US-1.5: Logout & Session Expiration ✅

- `POST /api/v1/auth/logout` – Cookie per `response.delete_cookie()` gelöscht
- JWT-Ablauf: 7 Tage (`JWT_EXPIRE_DAYS`)

### US-1.6: Multi-Case Dashboard ✅

- `GET /api/v1/cases` – eigene Cases nach Datum sortiert, mit `network_operator` + `document_count`
- `POST /api/v1/cases` – neuen DRAFT-Fall anlegen

### US-1.7: DSGVO Hard-Delete ✅

- `DELETE /api/v1/cases/{case_id}` – Reihenfolge: Storage-Stub → Qdrant-Stub → PostgreSQL CASCADE
- Delete-Confirmation-Modal im Frontend

### US-1.8: Passwort-Reset ✅

- `POST /api/v1/auth/forgot-password` – SHA-256-Token-Hash in DB, Resend-Mail oder DEV-Log
- `POST /api/v1/auth/reset-password` – Token verifizieren, Passwort neu setzen, Token invalidieren

---

## Neue Dateien (EPIC 4 & 5)

| Datei                                                    | Inhalt                                       |
| -------------------------------------------------------- | -------------------------------------------- |
| `backend/app/agents/nodes/extract_events.py`             | Event-Extraktion pro Dokument (Map-Phase)    |
| `backend/app/agents/nodes/build_master_timeline.py`      | Master-Chronologie & Gap-Analysis            |
| `backend/app/agents/nodes/incremental_update.py`         | Iterativer Upload / Merge-Logik              |
| `backend/app/api/v1/timeline.py`                         | Timeline CRUD + Refresh-Endpoint             |
| `backend/app/api/v1/checkout.py`                         | Stripe Checkout + Webhook                    |
| `backend/tests/test_epic4.py`                            | Tests für EPIC 4 (Chronologie)               |
| `backend/tests/test_epic5.py`                            | Tests für EPIC 5 (Checkout & Monetization)   |
| `frontend/src/features/case/steps/TimelineStep.tsx`      | Timeline-UI mit Polling, Edit/Delete, Gaps   |
| `frontend/src/components/AddEventModal.tsx`              | Modal für manuelle Ereignisse                |

---

## Nächste sinnvolle Schritte (nach Priorität)

1. **EPIC 6** implementieren: PDF-Dossier-Generierung (weasyprint / reportlab)
2. **React Router** Migration: State-basiertes Routing → React Router v6
3. **US-5.5** verifizieren: Stripe-Dashboard-Konfiguration (Steuer, Rechnung, Branding)

---

## Infrastruktur

| Komponente           | Status                                                    |
| -------------------- | --------------------------------------------------------- |
| `docker-compose.yml` | Vollständig: PostgreSQL, MinIO, Qdrant, Backend, Frontend |
| `alembic/`           | Vollständiges Setup mit initialer Migration               |
| GitHub Actions (CI)  | Tests + Docker Build/Push zu GHCR                         |
| Kubernetes Manifests | Vorhanden, Deployment in CI auskommentiert                |
