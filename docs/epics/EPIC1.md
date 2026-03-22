# EPIC 1: User Onboarding & Session Management

## 📋 Überblick

**Beschreibung:**
Das System bietet einen sicheren Zugang via E-Mail und Passwort. Nach der Authentifizierung landen Nutzer in einem persönlichen Dashboard, in dem sie mehrere rechtliche Konflikte (Cases) parallel verwalten können. Mandantenfähigkeit (Tenant Isolation) stellt sicher, dass Nutzer nur ihre eigenen Daten sehen.

**Business Value:**

- Sichere, DSGVO-konforme Nutzerverwaltung mit Hard-Delete-Funktion
- Vertrauensbasis für sensible Rechtsdaten durch JWT + HttpOnly-Cookies (XSS-Schutz)
- Multi-Case-Dashboard ermöglicht parallele Fallverwaltung und skalierbare Nutzererfahrung

**Tech Notes:**

- **Passwort-Sicherheit:** bcrypt / passlib im FastAPI-Backend – niemals Klartext
- **Session-Management:** Stateful via JWT, gespeichert in Secure + HttpOnly Cookies
- **Datenbank:** `users`-Tabelle (id, email, hashed_password, created_at); `CaseState` erhält FK `user_id`
- **Mail-Provider:** Resend (kostenloses Kontingent reicht für MVP)

**Zeitschätzung:** ~55–65 Stunden

---

## 🎯 Tickets in diesem Epic

### US-1.1: Setup – DB-Schema & Security Foundation

**Status:** Backlog
**Aufwand:** 6 Stunden
**Assignee:** –
**Dependencies:** Keine
**Blocking:** US-1.2, US-1.3, US-1.4, US-1.5, US-1.6, US-1.7, US-1.8

**Beschreibung:**
Als Entwickler muss ich das Datenbankschema für Nutzerkonten und die grundlegende Kryptografie einrichten, bevor User sich registrieren können.

**Akzeptanzkriterien:**

- [ ] Datenbank enthält Tabelle `users` (id, email [unique], hashed_password, created_at)
- [ ] `CaseState`-Entität / `cases`-Tabelle erhält Foreign Key `user_id`
- [ ] Utility-Funktionen `hash_password` und `verify_password` sind in `app/core/security.py` implementiert

**Implementierungs-Notizen:**

- Code-Path: `app/core/security.py` (Kryptografie), `app/models/` (DB-Schemas)
- Komponenten: passlib/bcrypt, SQLAlchemy-Migration
- Migration via Alembic: neue Tabelle + FK auf bestehende `cases`-Tabelle

---

### US-1.2: Registrierung (Sign Up)

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-1.1
**Blocking:** US-1.3

**Beschreibung:**
Als neuer Nutzer möchte ich mir ein Konto mit E-Mail und Passwort erstellen, um meine Fälle dauerhaft und unkompliziert speichern zu können.

**Akzeptanzkriterien:**

- [ ] UI bietet Formular mit Feldern: E-Mail, Passwort, Passwort-Bestätigung
- [ ] Backend lehnt Passwörter < 8 Zeichen ab
- [ ] Formular enthält Pflicht-Checkbox: „Ich akzeptiere AGB und Datenschutzerklärung" (mit Links)
- [ ] Bei Erfolg: User wird mit gehashtem Passwort in DB gespeichert
- [ ] Bei bereits existierender E-Mail: generische Fehlermeldung „E-Mail wird bereits verwendet"
- [ ] Nach Registrierung: direkter Login (Session-Cookie gesetzt) + Redirect ins leere Dashboard

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/auth.py` (POST /auth/register), Frontend: `pages/register.tsx`
- Komponenten: Pydantic-Validator, FastAPI-Router, DB-Session
- API: POST `/api/v1/auth/register` → 201 Created + Set-Cookie

---

### US-1.3: Login & Session-Erstellung (Sign In)

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-1.1, US-1.2
**Blocking:** US-1.4, US-1.5, US-1.6

**Beschreibung:**
Als bestehender Nutzer möchte ich mich mit E-Mail und Passwort einloggen, um auf meine gespeicherten Fälle zuzugreifen.

**Akzeptanzkriterien:**

- [ ] UI bietet Login-Formular (E-Mail, Passwort)
- [ ] System prüft Passwort-Hash gegen die Datenbank
- [ ] Bei falschen Daten: neutrale Meldung „E-Mail oder Passwort falsch" (kein Account-Enumeration-Leak)
- [ ] Bei Erfolg: JWT wird generiert und als HttpOnly + Secure Cookie gesendet
- [ ] Brute-Force-Schutz: max. 5 fehlgeschlagene Versuche / IP / 15 Minuten (Rate Limiting auf Login-Route)

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/auth.py` (POST /auth/login)
- Komponenten: python-jose (JWT), slowapi oder fastapi-limiter (Rate Limiting)
- API: POST `/api/v1/auth/login` → 200 OK + Set-Cookie (HttpOnly, Secure, SameSite=Strict)

---

### US-1.4: API-Security & Tenant Isolation

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-1.3
**Blocking:** US-1.6, US-1.7

**Beschreibung:**
Als Systembetreiber muss ich sicherstellen, dass Nutzer über die API ausschließlich auf ihre eigenen Fälle zugreifen können.

**Akzeptanzkriterien:**

- [ ] `Depends(get_current_user)` extrahiert und verifiziert JWT-Token aus Cookie bei jedem geschützten API-Call
- [ ] Bei GET `/api/v1/workflows/{case_id}` wird geprüft, ob `case_id` zur `user_id` der Session gehört
- [ ] Fehlgeschlagene Prüfung (fremder Case): Antwort ist `404 Not Found` (nicht `403 Forbidden`)

**Implementierungs-Notizen:**

- Code-Path: `app/core/dependencies.py` (`get_current_user`), alle geschützten Router
- Komponenten: FastAPI `Depends`, Cookie-Extraktion, DB-Lookup
- Sicherheitsprinzip: 404 statt 403 verhindert Informationsleak über existierende Case-IDs

---

### US-1.5: Logout & Session Expiration

**Status:** Backlog
**Aufwand:** 4 Stunden
**Assignee:** –
**Dependencies:** US-1.3, US-1.4
**Blocking:** –

**Beschreibung:**
Als Nutzer möchte ich mich aktiv abmelden können und nach längerer Inaktivität automatisch abgemeldet werden, um meine Daten zu schützen.

**Akzeptanzkriterien:**

- [ ] Dashboard zeigt deutlich sichtbaren „Abmelden"-Button
- [ ] Klick ruft Backend-Endpoint auf, der das HttpOnly-Cookie löscht/invalidiert
- [ ] Nutzer wird nach Logout auf Landingpage weitergeleitet
- [ ] JWT/Cookie hat maximale Lebensdauer von 7 Tagen; danach wird erneuter Login verlangt

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/auth.py` (POST /auth/logout)
- Komponenten: Cookie-Delete via `response.delete_cookie()`
- JWT `exp`-Claim auf 7 Tage setzen; Client-seitig kein Token-Refresh nötig (MVP)

---

### US-1.6: Multi-Case Dashboard

**Status:** Backlog
**Aufwand:** 10 Stunden
**Assignee:** –
**Dependencies:** US-1.3, US-1.4
**Blocking:** US-1.7

**Beschreibung:**
Als eingeloggter Nutzer möchte ich eine Übersicht meiner bestehenden Fälle sehen und einen neuen Fall starten können.

**Akzeptanzkriterien:**

- [ ] Route `/dashboard` ruft alle Cases des eingeloggten Nutzers (`user_id`) ab und stellt sie als Liste/Grid dar
- [ ] Jeder Case zeigt Metadaten: Erstelldatum, Status (Draft / Analyzing), Netzbetreiber/Anbieter (falls vorhanden)
- [ ] Button „Neuen Fall starten" ist sichtbar
- [ ] Klick: Backend generiert neue `case_id` (verknüpft mit User), speichert in DB, Redirect zu Document-Upload-Flow (Epic 2)

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/cases.py` (GET /cases, POST /cases), Frontend: `pages/dashboard.tsx`
- Komponenten: React Grid/List, FastAPI-Router, DB-Query mit `WHERE user_id = current_user.id`
- API: GET `/api/v1/cases` → Array of CaseSummary DTOs

---

### US-1.7: Data Deletion (DSGVO Hard-Delete)

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-1.4, US-1.6
**Blocking:** –

**Beschreibung:**
Als Nutzer möchte ich einen spezifischen Fall und alle zugehörigen Daten permanent löschen können.

**Akzeptanzkriterien:**

- [ ] Jeder Case im Dashboard hat Option „Fall unwiderruflich löschen" (z.B. Drei-Punkte-Menü)
- [ ] Warn-Modal verlangt explizite Bestätigung: „Diese Aktion kann nicht rückgängig gemacht werden"
- [ ] Nach Bestätigung: Hard-Delete aus Postgres (Metadaten + State)
- [ ] Nach Bestätigung: Vektor-Embeddings aus Qdrant löschen
- [ ] Nach Bestätigung: Physische PDF/Bilder aus Storage löschen
- [ ] Dashboard lädt neu; der Fall ist verschwunden

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/cases.py` (DELETE /cases/{case_id})
- Komponenten: Qdrant-Client (delete_points), Storage-Client (delete_object), DB-Transaction
- Reihenfolge: erst Storage → Qdrant → Postgres (von außen nach innen)

---

### US-1.8: Passwort vergessen (Reset-Flow)

**Status:** Backlog
**Aufwand:** 10 Stunden
**Assignee:** –
**Dependencies:** US-1.1
**Blocking:** –

**Beschreibung:**
Als Nutzer, der sein Passwort vergessen hat, möchte ich dieses über einen sicheren Link an meine E-Mail-Adresse zurücksetzen können.

**Akzeptanzkriterien:**

- [ ] Login-Seite hat Link „Passwort vergessen" → Eingabefeld für E-Mail-Adresse
- [ ] Backend generiert sicheres Reset-Token (Gültigkeit: 15 Minuten), speichert Hash in DB, triggert Resend-Mail
- [ ] UI zeigt sofort: „Falls ein Account existiert, wurde eine E-Mail gesendet" (unabhängig ob E-Mail registriert ist)
- [ ] Nutzer klickt Link (`/reset-password?token=...`) → kann neues Passwort eingeben
- [ ] Nach Speichern: altes Token wird invalidiert, neues Passwort gehasht in DB geschrieben

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/auth.py` (POST /auth/forgot-password, POST /auth/reset-password)
- Komponenten: `secrets.token_urlsafe()`, Resend SDK, Token-Hash in `password_reset_tokens`-Tabelle
- Token-Hash: SHA-256 des Raw-Tokens in DB speichern (niemals Raw-Token)

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
US-1.1 (DB-Schema & Security Foundation)
├─ Keine Dependencies
├─ Blocking für: US-1.2, US-1.3, US-1.8

US-1.2 (Registrierung)
├─ Abhängig von: US-1.1
├─ Blocking für: US-1.3

US-1.3 (Login & Session)
├─ Abhängig von: US-1.1, US-1.2
├─ Blocking für: US-1.4, US-1.5, US-1.6

US-1.4 (API-Security & Tenant Isolation)
├─ Abhängig von: US-1.3
├─ Blocking für: US-1.6, US-1.7

US-1.5 (Logout & Session Expiration)
├─ Abhängig von: US-1.3, US-1.4
├─ Blocking für: –

US-1.6 (Multi-Case Dashboard)
├─ Abhängig von: US-1.3, US-1.4
├─ Blocking für: US-1.7

US-1.7 (DSGVO Hard-Delete)
├─ Abhängig von: US-1.4, US-1.6
├─ Blocking für: –

US-1.8 (Passwort-Reset)
├─ Abhängig von: US-1.1
├─ Blocking für: –
```
