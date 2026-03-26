# Progress.md – Resovva.de

Stand: 2026-03-26

---

## Gesamtstatus: EPIC 1 ✅ · EPIC 2 ✅ · EPIC 3 ✅ (US-3.3 Frontend partiell)

---

---

## EPIC 3: AI Analysis & Extraction Engine ✅ (US-3.3 Frontend partiell)

### US-3.1: RAG Foundation ✅

- `core/rag.py`: `chunk_and_embed()`, `search_rag()`, `search_rag_with_meta()` — Chunking (1000 Zeichen, 100 Overlap), OpenAI `text-embedding-3-small`, Qdrant-Speicherung
- `infrastructure/qdrant_client.py`: Collection-Management (1536-dim), Upsert, semantische Suche mit `case_id`-Filter, DSGVO-Delete

### US-3.2: Core Entity Extraction ✅

- `agents/nodes/extract.py`: 3 gezielte RAG-Suchen (Zählernummer, MaLo, Betrag), strikt `gpt-4o-mini` mit `with_structured_output`
- Confidence-Scoring: Regex-Match 1.0 · LLM-only 0.6 · fehlend 0.0
- Source-Tracking: `source_document_id` + `source_text_snippet` pro Feld

### US-3.3: Early Exit & Missing Data UI ⚠️ Backend ✅ · Frontend partiell

- `agents/graph.py`: Conditional Edge `should_request_more_data()` — wenn `meter_number IS NULL AND malo_id IS NULL` → Pause
- Case-Status → `WAITING_FOR_USER`; LangGraph-Interrupt vor `confirm`-Node
- **Frontend-Lücke:** Spezifische "Wir konnten keine Zählernummer finden."-Meldung + "Weiteres Dokument hochladen"-Button fehlen; die bestehende `review`-Phase deckt manuelle Korrektur ab

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

## Neue Dateien (EPIC 1)

| Datei                                            | Inhalt                        |
| ------------------------------------------------ | ----------------------------- |
| `backend/app/api/v1/auth.py`                     | Vollständiger Auth-Router     |
| `backend/app/api/v1/cases.py`                    | Cases CRUD + Hard-Delete      |
| `backend/app/infrastructure/database.py`         | SQLAlchemy Session Factory    |
| `backend/app/core/limiter.py`                    | slowapi Singleton             |
| `backend/alembic/env.py`                         | Alembic Migration-Environment |
| `backend/alembic/versions/001_initial_schema.py` | Initiale DB-Migration         |
| `backend/alembic.ini`                            | Alembic-Konfiguration         |

## Geänderte Dateien (EPIC 1)

| Datei                                           | Änderungen                                                                    |
| ----------------------------------------------- | ----------------------------------------------------------------------------- |
| `backend/app/main.py`                           | Auth/Cases Router, CORS, Rate Limiter                                         |
| `backend/app/core/security.py`                  | hash_password, verify_password, JWT-Funktionen                                |
| `backend/app/core/config.py`                    | DATABASE_URL, SECRET_KEY, JWT_EXPIRE_DAYS, ALLOWED_ORIGINS, RESEND            |
| `backend/app/api/dependencies.py`               | Vollständige get_current_user Implementierung                                 |
| `backend/app/domain/models/db.py`               | PasswordResetToken Tabelle                                                    |
| `backend/pyproject.toml`                        | Neue Abhängigkeiten                                                           |
| `backend/.env.example`                          | Alle neuen Env-Variablen                                                      |
| `frontend/src/types/index.ts`                   | ApiCase, mapApiCase, erweiterte CaseStatus                                    |
| `frontend/src/services/api.ts`                  | credentials: "include", echte Auth-Types, logout/forgotPassword/resetPassword |
| `frontend/src/features/auth/Login.tsx`          | Echte API-Calls, Passwort-Bestätigung, Forgot-Password-Tab                    |
| `frontend/src/features/dashboard/Dashboard.tsx` | Echte Cases via API, Delete-Modal, Logout                                     |

---

## Nächste Migrations-Schritte

```bash
# Einmalig nach dem Start (im backend/ Verzeichnis):
cd backend
alembic upgrade head
```

---

## Backend – Gesamtstatus

### Vollständig implementiert

| Modul                                          | Beschreibung                                              |
| ---------------------------------------------- | --------------------------------------------------------- |
| `main.py`                                      | FastAPI App, Router, CORS, Rate Limiter                   |
| `core/config.py`                               | Pydantic Settings, alle Konfigurationsfelder              |
| `core/security.py`                             | PII-Maskierung + bcrypt + JWT                             |
| `core/limiter.py`                              | Rate-Limiter-Singleton                                    |
| `domain/models/db.py`                          | User, Case, Document, ChronologyEvent, PasswordResetToken |
| `domain/models/document.py`                    | ExtractedEntity, DocumentInput                            |
| `domain/models/case.py`                        | CaseStatus, CaseState                                     |
| `domain/models/timeline.py`                    | ChronologyItem                                            |
| `domain/services/document_ingest.py`           | Multi-Backend PDF-Parsing                                 |
| `domain/services/pdf_parsing.py`               | Async-Wrapper                                             |
| `infrastructure/azure_openai.py`               | LLM Factory                                               |
| `infrastructure/checkpointer.py`               | PostgresSaver / MemorySaver                               |
| `infrastructure/database.py`                   | SQLAlchemy Session Factory                                |
| `api/dependencies.py`                          | get_current_user, CurrentUser                             |
| `api/v1/auth.py`                               | Register, Login, Logout, ForgotPassword, ResetPassword    |
| `api/v1/cases.py`                              | GET/POST /cases, DELETE /cases/{id}                       |
| `api/v1/documents.py`                          | POST /documents/upload (lokale Speicherung)               |
| `agents/state.py`                              | AgentState TypedDict                                      |
| `agents/graph.py` → Nodes `ingest` & `extract` | LLM-Extraktion                                            |

### Teilweise implementiert

| Modul                                           | Was fehlt                                         |
| ----------------------------------------------- | ------------------------------------------------- |
| `api/v1/workflows.py`                           | `POST /run` funktioniert; `POST /resume` ist Stub |
| `agents/graph.py` → Nodes `chronology` & `gaps` | Keine echte Logik                                 |
| `domain/services/chronology_builder.py`         | Gap-Erkennung nur per Flag                        |

### Stubs / Platzhalter

| Modul                                         | Status                               |
| --------------------------------------------- | ------------------------------------ |
| `infrastructure/azure_openai.py` → Embeddings | Deaktiviert (OpenAI SDK direkt genutzt) |

### Fehlende kritische Features (Backend)

- **Dossier-Generierung**: Kein PDF-Generator (Epic 6)
- **Stripe-Payment**: Keine Integration (Epic 5)
- **Tests**: Nur `test_health()` — keine Tests für Auth, Cases, Workflows
- **US-3.3 Frontend**: "Wir konnten keine Zählernummer finden."-UI mit zwei Optionen fehlt

---

## Frontend – Gesamtstatus

### Vollständig implementiert

| Bereich                 | Beschreibung                                                   |
| ----------------------- | -------------------------------------------------------------- |
| **Design System**       | Tokens (Farben, Typografie, Shadows) in `theme/tokens.ts`      |
| **Komponenten**         | Button, Badge, Card, Icon, Nav                                 |
| **Routing**             | State-basiertes Routing via `usePageState`                     |
| **services/api.ts**     | Typisierter HTTP-Client mit `credentials: "include"`           |
| **Login/Register**      | Echte API-Calls, Validierung, Passwort-Bestätigung             |
| **Forgot-Password**     | Tab-basierter Flow im Login-Screen                             |
| **Dashboard**           | Echte Cases via API, Loading/Empty State, Delete-Modal, Logout |
| **Landing Page**        | Vollständig                                                    |
| **Case Flow (4 Steps)** | UI vollständig, kein Backend-Connect                           |
| **Dossier Screen**      | Animierter Fortschritt, kein Backend-Connect                   |
| **Preisseite**          | Marketing-Copy vollständig                                     |

### Fehlende kritische Features (Frontend)

- **Datei-Upload**: UI vorhanden, kein `POST /cases/{id}/documents` Call
- **Workflow-Trigger**: Analyse simuliert, kein `POST /workflows/run`
- **Passwort-Reset-Page**: `/reset-password?token=...` Seite fehlt noch
- **React Router**: State-basiert, TODO für Migration

---

## Infrastruktur

| Komponente           | Status                                                    |
| -------------------- | --------------------------------------------------------- |
| `docker-compose.yml` | Vollständig: PostgreSQL, MinIO, Qdrant, Backend, Frontend |
| `alembic/`           | Neu: vollständiges Setup mit initialer Migration          |
| GitHub Actions (CI)  | Tests + Docker Build/Push zu GHCR                         |
| Kubernetes Manifests | Vorhanden, Deployment in CI auskommentiert                |

---

## Nächste sinnvolle Schritte (nach Priorität)

1. **US-3.3 Frontend** vervollständigen: "Keine Zählernummer"-Modal mit Upload-Option
2. **Auth-Tests** schreiben (Register, Login, Logout, Tenant Isolation)
3. **EPIC 4** implementieren: Chronologie + Gap-Erkennung (Backend-Nodes `chronology` & `gaps`)
4. **EPIC 5** implementieren: Stripe-Checkout
5. **EPIC 6** implementieren: PDF-Dossier-Generierung
