# EPIC 6: Dossier Generation & Export

## 📋 Überblick

**Beschreibung:**
In diesem finalen Schritt wird das Endprodukt erzeugt, für das der Nutzer bezahlt hat. Nach Stripe-Webhook-Bestätigung startet ein asynchroner Hintergrundprozess: Jinja2-Templates werden mit bestätigten Stammdaten und Chronologie befüllt, via WeasyPrint zu einem Haupt-PDF gerendert, alle Original-Uploads gestempelt (Anlage 1, 2, …) und zu einem einzigen Master-PDF zusammengefügt. Der Nutzer erhält eine Benachrichtigungsmail und lädt das Dossier sicher via Presigned S3 URL herunter.

**Business Value:**

- Das fertige Master-PDF ist das eigentliche Produkt – juristisch verwertbar, vollständig, in einer einzigen Datei
- Vollautomatischer Workflow ohne manuelle Schritte nach der Zahlung – skalierbar auf beliebig viele gleichzeitige Fälle
- Presigned URLs und Auth-Guard verhindern öffentlich zugängliche Dokumente – maximaler Datenschutz

**Tech Notes:**

- **Template Engine:** Jinja2 (HTML/CSS) in `app/templates/` – anpassbar ohne Programmierkenntnisse
- **PDF-Rendering:** WeasyPrint (HTML → PDF, saubere Typografie + CSS-Seitenumbrüche)
- **Merging & Stamping:** pypdf oder PyMuPDF; Bildkonvertierung via Pillow (PIL) → A4-PDF
- **Zustellung:** Resend (Benachrichtigungsmail); Download via zeitlich limitierter Presigned S3 URL hinter `Depends(get_current_user)`

**Zeitschätzung:** ~48–56 Stunden

---

## 🎯 Tickets in diesem Epic

### US-6.1: Setup – Template Engine & Basis-Layout

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** Epic 5 – US-5.2 (Zahlung bestätigt, PAID-Status liegt vor)
**Blocking:** US-6.2

**Beschreibung:**
Als Legal/Content Manager möchte ich HTML-Templates für das Dossier nutzen, um rechtliche Textbausteine schnell und ohne Programmierkenntnisse anpassen zu können.

**Akzeptanzkriterien:**

- [ ] Jinja2 ist ins FastAPI-Projekt integriert, Templates liegen unter `app/templates/`
- [ ] Basis-HTML/CSS-Template enthält: Kopfzeile mit Logo, Briefkopf, Datum, saubere Typografie
- [ ] Template enthält Variablen-Platzhalter für: Absender (Nutzer), Empfänger (Netzbetreiber), Datum, Zählernummer, MaLo, Betrag und die Chronologie (als HTML-Tabelle)

**Implementierungs-Notizen:**

- Code-Path: `app/templates/dossier_main.html`, `app/templates/base.html`
- Komponenten: `jinja2`, `weasyprint` (wird in US-6.2 genutzt, aber CSS hier definieren)
- CSS: CMYK-freundliche Farben, A4-Format (`@page { size: A4; margin: 2cm; }`), serifenlose Schrift (Arial/Helvetica)
- Template-Variablen: `{{ user.name }}`, `{{ network_operator }}`, `{{ meter_number }}`, `{{ malo_id }}`, `{{ dispute_amount }}`, `{{ timeline | safe }}`
- Testrender: Template mit Dummy-Daten befüllen und manuell als HTML im Browser prüfen bevor WeasyPrint involviert wird

---

### US-6.2: PDF-Rendering (WeasyPrint)

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-6.1
**Blocking:** US-6.3, US-6.4

**Beschreibung:**
Als Systembetreiber möchte ich die mit Daten befüllten HTML-Templates in ein professionelles, unveränderbares PDF-Format umwandeln.

**Akzeptanzkriterien:**

- [ ] WeasyPrint ist integriert als PDF-Generator
- [ ] `DossierGenerator`-Service nimmt aktuellen `CaseState` aus Postgres, füllt Jinja2-Template und generiert Haupt-PDF (Anschreiben + Chronologie) im Arbeitsspeicher
- [ ] Seitenumbrüche in der Chronologie-Tabelle werden sauber gerendert (`page-break-inside: avoid`)

**Implementierungs-Notizen:**

- Code-Path: `app/services/dossier_generator.py`
- WeasyPrint-Call: `HTML(string=rendered_html).write_pdf()` → gibt `bytes` zurück (kein Tempfile nötig)
- WeasyPrint benötigt System-Dependencies: `libpango`, `libcairo` – in `Dockerfile` ergänzen
- Haupt-PDF enthält: Deckblatt (Seite 1), Anschreiben (Seite 2), Chronologie-Tabelle (Seite 3+)
- Chronologie als `<table>` mit `<tr style="page-break-inside: avoid">` pro Zeile

---

### US-6.3: Evidence Compiler (Bilder wandeln, Stempeln & Mergen)

**Status:** Backlog
**Aufwand:** 14 Stunden
**Assignee:** –
**Dependencies:** US-6.2
**Blocking:** US-6.4

**Beschreibung:**
Als Nutzer möchte ich, dass alle meine hochgeladenen Original-Belege automatisch mit „Anlage X" gestempelt und an mein Anschreiben angehängt werden, damit ich nur eine einzige Datei verschicken muss.

**Akzeptanzkriterien:**

- [ ] Background-Task lädt alle Original-Dateien des Falls aus S3 (`StorageService`)
- [ ] **Bild-Konvertierung:** `.jpg` und `.png` werden in A4-PDF konvertiert
- [ ] **Stempeln:** Jedes Anlage-Dokument erhält rechts oben einen Stempel (z.B. roter Text: „Anlage 1", „Anlage 2") – korrespondierend zur Chronologie-Referenz
- [ ] **Merging:** Haupt-PDF (US-6.2) + alle gestempelten Anlagen → eine Datei `dossier_master.pdf` → zurück in S3

**Implementierungs-Notizen:**

- Code-Path: `app/services/evidence_compiler.py`
- Bild → PDF: `PIL.Image.open(img).save(pdf_path, "PDF", resolution=150.0)` dann via pypdf einlesen
- Stempeln: pypdf `PageObject` + `canvas`-Overlay (reportlab) oder PyMuPDF `page.insert_text()` – PyMuPDF ist einfacher
- Stempel-Koordinaten: `x=A4.width - 80`, `y=A4.height - 40` (rechts oben, 1cm Rand)
- Merge-Reihenfolge: [Haupt-PDF, Anlage 1, Anlage 2, …] – Reihenfolge nach `document.upload_order` in DB
- Finales PDF unter `{case_id}/dossier_master.pdf` in S3 speichern

---

### US-6.4: Asynchroner Workflow & Status-Updates

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-6.2, US-6.3
**Blocking:** US-6.5

**Beschreibung:**
Als Nutzer möchte ich nach der Zahlung sehen, dass mein Dossier gerade generiert wird, da dieser komplexe Prozess einige Sekunden dauern kann.

**Akzeptanzkriterien:**

- [ ] Stripe-Webhook (Epic 5 – US-5.2) setzt Case-Status auf `GENERATING_DOSSIER` und triggert PDF-Erstellungs-Task (US-6.1–6.3) im Hintergrund
- [ ] Frontend pollt GET `/api/v1/cases/{case_id}` auf Status-Änderungen
- [ ] Schlägt die Generierung fehl: Status → `ERROR_GENERATION` (Admin/Support kann Task neu anstoßen)
- [ ] Bei Erfolg: Status → `COMPLETED`

**Implementierungs-Notizen:**

- Code-Path: `app/workers/dossier_worker.py`, `app/api/routes/cases.py`
- FastAPI `BackgroundTasks` oder Celery (wenn Task-Queue bereits vorhanden) für asynchronen Start
- Try/Except um den gesamten Generierungsprozess: bei Exception → `ERROR_GENERATION` + Fehlerdetails in `cases.error_log` (JSONB)
- Admin-Endpoint: POST `/api/v1/admin/cases/{case_id}/retry-generation` (geschützt via Admin-Role)
- Polling-Intervall im Frontend: 3 Sekunden (großzügiger als Epic 2, da Generierung länger dauert)
- Status-Progressanzeige im Frontend: `GENERATING_DOSSIER` → animierter Fortschrittsbalken mit Text „Dein Dossier wird erstellt… das dauert ca. 30 Sekunden."

---

### US-6.5: Zustellung & Sicherer Download

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-6.4
**Blocking:** –

**Beschreibung:**
Als Nutzer möchte ich per E-Mail informiert werden, sobald mein fertiges Dossier bereitsteht, und es sicher in meinem Konto herunterladen können.

**Akzeptanzkriterien:**

- [ ] Bei Status `COMPLETED`: Backend sendet E-Mail via Resend: „Dein Resovva-Dossier ist fertig. Klicke hier, um es in deinem Dashboard herunterzuladen."
- [ ] E-Mail-Link führt zu `/dashboard/case/{case_id}` (Login erforderlich)
- [ ] Dashboard zeigt prominenten Button „Dossier herunterladen"
- [ ] Klick ruft GET `/api/v1/cases/{case_id}/download` auf (geschützt via `Depends(get_current_user)`)
- [ ] Endpoint generiert eine auf **5 Minuten befristete Presigned S3 URL** und leitet Browser zum Download weiter – keine öffentlichen S3-Links

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/cases.py` (GET /download), `app/infrastructure/storage.py` (Presigned URL)
- Presigned URL: `boto3_client.generate_presigned_url("get_object", Params={...}, ExpiresIn=300)`
- Response: `302 Redirect` zur Presigned URL (nicht die URL an Frontend zurückgeben – verhindert URL-Sharing)
- Tenant-Check: zwingend prüfen ob `case_id` zum eingeloggten User gehört bevor URL generiert wird (analog US-1.4)
- E-Mail-Template: `app/templates/email_dossier_ready.html` (Jinja2, bereits installiert)
- Download-Button im Dashboard: nur sichtbar wenn `case.status == COMPLETED`

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
US-6.1 (Template Engine & Basis-Layout)
├─ Abhängig von: Epic 5 – US-5.2 (PAID-Status)
├─ Blocking für: US-6.2

US-6.2 (PDF-Rendering / WeasyPrint)
├─ Abhängig von: US-6.1
├─ Blocking für: US-6.3, US-6.4

US-6.3 (Evidence Compiler / Stempeln & Mergen)
├─ Abhängig von: US-6.2
├─ Blocking für: US-6.4

US-6.4 (Asynchroner Workflow & Status-Updates)
├─ Abhängig von: US-6.2, US-6.3
├─ Blocking für: US-6.5

US-6.5 (Zustellung & Sicherer Download)
├─ Abhängig von: US-6.4
├─ Blocking für: – (Produkt fertig 🎉)
```
