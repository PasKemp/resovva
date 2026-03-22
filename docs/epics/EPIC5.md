# EPIC 5: Checkout & Monetization (Die Paywall)

## 📋 Überblick

**Beschreibung:**
Nach der bestätigten Chronologie greift die Monetarisierungsphase. Das System präsentiert eine wertorientierte Zusammenfassung und fordert eine Einmalzahlung von 20,00 € (Pay-per-Case). Zahlungsabwicklung, Promo-Codes und automatische Rechnungsstellung laufen komplett über Stripe Checkout. Der Nutzer verzichtet rechtlich bindend auf sein Widerrufsrecht. Die Freischaltung für Epic 6 erfolgt manipulationssicher via Stripe Webhooks.

**Business Value:**

- Pay-per-Case-Modell senkt Einstiegshürde: kein Abo, kein Risiko für den Nutzer
- Vollständige Stripe-Automatisierung: Rechnungsstellung, MwSt, Promo-Codes – null manueller Aufwand
- Webhook-basierte Freischaltung ist manipulationssicher – kein Client-seitiger Zahlungsstatus dem man vertrauen muss

**Tech Notes:**

- **Zahlungsanbieter:** Stripe Checkout API (Hosted Checkout Page)
- **Tracking:** `case_id` + `user_id` zwingend in `metadata` / `client_reference_id` der Stripe-Session
- **Webhook-Sicherheit:** Signatur-Verifikation via `stripe-signature` Header + Webhook-Secret (Pflicht, kein Optional)
- **Status-Modell:** `ANALYZING` → `PAYMENT_PENDING` (Checkout gestartet) → `PAID` (Webhook empfangen)

**Zeitschätzung:** ~30–38 Stunden

---

## 🎯 Tickets in diesem Epic

### US-5.1: Setup – Stripe Checkout Session (Backend)

**Status:** Backlog
**Aufwand:** 6 Stunden
**Assignee:** –
**Dependencies:** Epic 4 – US-4.5 (Chronologie bestätigt, Case-Status bereit)
**Blocking:** US-5.3, US-5.4

**Beschreibung:**
Als Entwickler muss ich eine Schnittstelle zu Stripe bauen, die eine sichere Bezahlseite für einen spezifischen Fall generiert, damit der Nutzer dort seine Zahlungsdaten eingeben kann.

**Akzeptanzkriterien:**

- [ ] API bietet Endpoint POST `/api/v1/cases/{case_id}/checkout`
- [ ] Backend erstellt via Stripe API eine `checkout.session` für ein Einmalprodukt (20,00 €)
- [ ] `case_id` und `user_id` werden zwingend in `metadata` oder als `client_reference_id` der Session gespeichert
- [ ] `allow_promotion_codes: true` ist gesetzt – Promo-Codes können vom Nutzer auf der Stripe-Seite eingegeben werden
- [ ] API gibt `checkout_url` zurück; Case-Status wechselt auf `PAYMENT_PENDING`

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/checkout.py`, `app/infrastructure/stripe_client.py`
- Komponenten: `stripe` Python SDK (`stripe.checkout.Session.create()`)
- `success_url`: `/dashboard?payment=success&case_id={case_id}`
- `cancel_url`: `/dashboard?payment=cancelled&case_id={case_id}`
- Stripe-Keys in `.env`: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- Case-Status-Update und Session-Erstellung in einer DB-Transaktion (kein Partial State)

---

### US-5.2: Webhook-Handler für Zahlungsbestätigung (Backend)

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-5.1
**Blocking:** Epic 6 (Dossier-Generierung)

**Beschreibung:**
Als Systembetreiber muss mein Server verlässlich mitbekommen, wenn eine Zahlung bei Stripe erfolgreich war, um den Fall manipulationssicher freizuschalten.

**Akzeptanzkriterien:**

- [ ] API bietet Endpoint POST `/api/v1/webhooks/stripe`
- [ ] **Security:** Endpoint verifiziert Stripe-Webhook-Signatur (`stripe-signature` Header). Ungültige Signaturen → `400 Bad Request`
- [ ] Endpoint lauscht auf Event `checkout.session.completed`
- [ ] Bei Empfang: `case_id` aus `metadata` auslesen, Case-Status in DB auf `PAID` setzen
- [ ] (Bonus) Stripe `payment_intent`-ID wird am Case geloggt für Buchhaltungs-Referenzen

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/webhooks.py`
- Signatur-Verifikation: `stripe.Webhook.construct_event(payload, sig_header, webhook_secret)` – niemals skippen, auch nicht in Tests
- **Kritisch:** FastAPI-Endpoint muss den Raw-Request-Body lesen (`Request.body()`), **nicht** das geparste JSON – Stripe prüft die Signatur gegen den Raw-Payload
- Idempotenz: prüfen ob `case_id` bereits `PAID` ist bevor Update – Stripe kann Events doppelt senden
- Lokales Testing: `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe` (Stripe CLI)

---

### US-5.3: Paywall UI & Widerrufs-Verzicht (Frontend)

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-5.1
**Blocking:** US-5.4

**Beschreibung:**
Als Nutzer möchte ich klar verstehen, wofür ich 20 € bezahle, und ich muss rechtlich bindend dem sofortigen Start der Dienstleistung zustimmen.

**Akzeptanzkriterien:**

- [ ] Nach Bestätigung der Chronologie (Epic 4) landet Nutzer auf der Paywall-Seite
- [ ] UI zeigt wertorientierte Zusammenfassung: „Deine Chronologie ist fertig. Lass uns jetzt dein finales, juristisches Dossier generieren. Preis: 20,00 €"
- [ ] **Abmahn-Schutz:** Pflicht-Checkbox (nicht vorausgewählt): _„Ich verlange ausdrücklich, dass mit der Ausführung des Vertrags vor Ablauf der Widerrufsfrist begonnen wird. Mir ist bekannt, dass ich mit vollständiger Vertragserfüllung mein Widerrufsrecht verliere."_
- [ ] Button „Kostenpflichtig bestellen" ist deaktiviert bis Checkbox aktiviert ist
- [ ] Klick triggert US-5.1 und leitet Nutzer auf Stripe-URL weiter

**Implementierungs-Notizen:**

- Code-Path: Frontend: `pages/checkout.tsx`, `components/WiderrufsCheckbox.tsx`
- Checkbox darf unter **keinen Umständen** vorausgewählt sein (`defaultChecked={false}`) – juristisches Muss
- Checkbox-Text muss exakt wie oben formuliert sein (abgestimmt mit Rechtsberatung)
- Button-State: `disabled={!checkboxChecked || isLoading}`
- Nach Klick: Ladeindikator anzeigen bis `checkout_url` zurückkommt, dann `window.location.href = checkout_url`

---

### US-5.4: Abgebrochene Zahlungen & Dashboard-Retry

**Status:** Backlog
**Aufwand:** 4 Stunden
**Assignee:** –
**Dependencies:** US-5.1, US-5.3
**Blocking:** –

**Beschreibung:**
Als Nutzer, der den Bezahlvorgang versehentlich abgebrochen hat, möchte ich die Zahlung später aus meinem Dashboard heraus nachholen können, ohne den Fall neu anlegen zu müssen.

**Akzeptanzkriterien:**

- [ ] Nach Abbruch (Cancel-URL) landet Nutzer im Dashboard
- [ ] Fall zeigt Status „Zahlung ausstehend" (`PAYMENT_PENDING`) mit primärem Button „Zahlung abschließen"
- [ ] Klick generiert eine neue Stripe-Session (erneuter Aufruf von US-5.1) und leitet zurück zu Stripe
- [ ] Alte, abgebrochene Stripe-Session wird nicht wiederverwendet (Stripe-Sessions sind ohnehin 24h gültig, aber neue Session ist sauberer)

**Implementierungs-Notizen:**

- Code-Path: Wiederverwendung von `POST /api/v1/cases/{case_id}/checkout` aus US-5.1
- Dashboard zeigt Case-Status `PAYMENT_PENDING` mit gelbem Badge und CTA-Button
- Keine neue DB-Spalte nötig – `case_status` reicht als Signal
- `cancel_url` aus US-5.1 enthält `?payment=cancelled` → Dashboard liest Query-Param und zeigt einmaligen Hinweis-Toast: „Zahlung wurde abgebrochen. Du kannst es jederzeit erneut versuchen."

---

### US-5.5: Automatisierte Rechnungsstellung (Stripe Config)

**Status:** Backlog
**Aufwand:** 3 Stunden
**Assignee:** –
**Dependencies:** US-5.2
**Blocking:** –

**Beschreibung:**
Als Systembetreiber möchte ich keinen manuellen Aufwand mit Rechnungen haben, daher soll Stripe nach erfolgreicher Zahlung automatisch eine korrekte PDF-Rechnung an den Kunden schicken.

**Akzeptanzkriterien:**

- [ ] Im Stripe Dashboard ist automatische Rechnungserstellung („Invoicing") aktiviert
- [ ] Rechnungen enthalten Resovva-Logo, Firmenanschrift und weisen deutsche MwSt (19%) korrekt aus
- [ ] Kunde erhält Rechnung nach `checkout.session.completed` automatisch per E-Mail von Stripe

**Implementierungs-Notizen:**

- Kein Code – reine Stripe-Dashboard-Konfiguration
- Stripe → Settings → Invoices → „Automatically finalize and send invoices"
- Steuer: Stripe Tax aktivieren oder manuell 19% MwSt-Rate für Deutschland anlegen
- Branding: Stripe → Settings → Branding → Logo + Unternehmensfarbe + Adresse hinterlegen
- Checkpoint: Test-Zahlung durchführen und E-Mail-Eingang der Rechnung verifizieren bevor Ticket als Done markieren

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
US-5.1 (Stripe Checkout Session / Backend)
├─ Abhängig von: Epic 4 – US-4.5 (Chronologie bestätigt)
├─ Blocking für: US-5.3, US-5.4

US-5.2 (Webhook-Handler)
├─ Abhängig von: US-5.1
├─ Blocking für: US-5.5, Epic 6 (Dossier-Generierung)

US-5.3 (Paywall UI & Widerrufs-Verzicht)
├─ Abhängig von: US-5.1
├─ Blocking für: US-5.4

US-5.4 (Abgebrochene Zahlungen / Dashboard-Retry)
├─ Abhängig von: US-5.1, US-5.3
├─ Blocking für: –

US-5.5 (Automatisierte Rechnungsstellung)
├─ Abhängig von: US-5.2 (Stripe konfiguriert und getestet)
├─ Blocking für: –
```
