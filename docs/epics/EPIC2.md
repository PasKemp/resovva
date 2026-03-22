# EPIC 2: Document Ingestion & Privacy

## 📋 Überblick

**Beschreibung:**
Dieses Epic deckt den gesamten Prozess vom Nutzergerät bis zum sauberen, maschinenlesbaren Text ab. Nutzer können Dokumente (PDFs, Bilder) per PC oder via QR-Code-Scan direkt vom Smartphone hochladen. Das Backend extrahiert Text asynchron mit einer Fallback-Logik (pypdf → Azure) und schwärzt sensible Daten (IBAN, E-Mail) per Regex. Das Originaldokument bleibt unangetastet als Beweismittelanhang für das finale PDF-Dossier.

**Business Value:**

- Reibungsloser Multi-Device-Upload (PC + Smartphone via QR-Code) senkt die Einstiegshürde massiv
- Kosteneffizienz durch OCR-Fallback: Azure Document Intelligence wird nur bei Bedarf aufgerufen
- Sichtbares PII-Masking (Preview mit Highlighting) schafft Nutzervertrauen vor der KI-Analyse

**Tech Notes:**

- **Storage:** boto3 (AWS S3 SDK); MinIO-Container im lokalen Docker-Setup → kein Vendor-Lock-in
- **Async & Polling:** FastAPI `BackgroundTasks` triggern die OCR; Frontend fragt Status per REST-Polling ab
- **OCR-Fallback:** pypdf zuerst (kostenlos); Azure Document Intelligence nur bei Bild-PDFs / JPEGs
- **Datenschutz:** Regex-Masking direkt nach Textextraktion – das LLM sieht ausschließlich maskierten Text

**Zeitschätzung:** ~50–60 Stunden

---

## 🎯 Tickets in diesem Epic

### US-2.1: Setup – S3-kompatibler Storage Service

**Status:** Backlog
**Aufwand:** 6 Stunden
**Assignee:** –
**Dependencies:** Keine
**Blocking:** US-2.2, US-2.3, US-2.4, US-2.5

**Beschreibung:**
Als Entwickler muss ich eine S3-kompatible Speicherinfrastruktur aufsetzen, damit Uploads sicher, skalierbar und getrennt vom App-Container gespeichert werden (Vorbereitung für den Beweismittelanhang).

**Akzeptanzkriterien:**

- [ ] `docker-compose.yml` enthält MinIO-Service inkl. persistenter Volumes
- [ ] `StorageService` (Python-Klasse in `app/infrastructure/storage.py`) ist implementiert und nutzt boto3
- [ ] Service bietet Methoden: `upload_file`, `download_file`, `delete_file`
- [ ] S3-Credentials (Endpoint, Access Key, Secret Key, Bucket Name) werden über `.env` gesteuert

**Implementierungs-Notizen:**

- Code-Path: `app/infrastructure/storage.py`, `docker-compose.yml`
- Komponenten: boto3, MinIO Docker Image (`minio/minio`)
- `.env`-Keys: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_NAME`
- Bucket beim Start auto-erstellen falls nicht vorhanden (`create_bucket` mit `exist_ok=True`)

---

### US-2.2: Datei-Upload & Client-Side Compression

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-2.1
**Blocking:** US-2.3, US-2.4

**Beschreibung:**
Als Nutzer möchte ich Rechnungen und Verträge als PDF oder Bild hochladen können, ohne dass große Dateien den Server überlasten.

**Akzeptanzkriterien:**

- [ ] Frontend erlaubt Upload von `.pdf`, `.jpg`, `.jpeg`, `.png`
- [ ] Bilder werden im Browser vor dem Upload komprimiert (max. 2000px Breite, JPEG-Konvertierung, Qualität max. 80%)
- [ ] Hartes Dateigrößen-Limit von 10 MB pro Datei (nach Komprimierung) – erzwungen im Frontend **und** Backend
- [ ] Backend generiert eindeutigen Dateinamen (UUID) und speichert via `StorageService` unter Pfad `{case_id}/{uuid}.{ext}`

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/documents.py` (POST /cases/{case_id}/documents), Frontend: `components/FileUpload.tsx`
- Komponenten: browser-image-compression (npm), FastAPI `UploadFile`, python-magic (MIME-Validierung)
- Backend-Validierung: MIME-Type prüfen, nicht nur Dateiendung

---

### US-2.3: Cross-Device Upload (QR-Code Magic Flow)

**Status:** Backlog
**Aufwand:** 10 Stunden
**Assignee:** –
**Dependencies:** US-2.1, US-2.2
**Blocking:** –

**Beschreibung:**
Als Nutzer am PC möchte ich Papierdokumente schnell mit meinem Smartphone abfotografieren und direkt in meinen Fall einfügen können, ohne mir die Bilder selbst mailen zu müssen.

**Akzeptanzkriterien:**

- [ ] PC-Frontend bietet Button „Mit dem Handy scannen"
- [ ] Klick generiert im Backend ein kurzlebiges Upload-Token (Gültigkeit: 15 Minuten) für die spezifische `case_id`
- [ ] PC-Frontend zeigt QR-Code mit URL `resovva.de/mobile-upload?token=abc`
- [ ] Mobile Web-Ansicht öffnet sich beim Scan mit Kamera-Zugriff; Fotos werden inkl. Client-Compression (aus US-2.2) direkt an die API gesendet
- [ ] PC-Frontend pollt alle 2 Sekunden neue Dateien und zeigt hochgeladene Handy-Fotos sofort an

**Implementierungs-Notizen:**

- Code-Path: `app/api/routes/mobile_upload.py` (POST /upload-tokens, POST /mobile-upload)
- Komponenten: `qrcode` (Python, QR-Generierung), `secrets.token_urlsafe()` (Token), Frontend: `qrcode.react` (npm)
- Token-Tabelle in DB: `mobile_upload_tokens` (token_hash, case_id, expires_at, used)
- Polling-Endpoint: GET `/api/v1/cases/{case_id}/documents` → Liste aller Dokumente

---

### US-2.4: Async OCR-Worker & Fallback-Logik

**Status:** Backlog
**Aufwand:** 12 Stunden
**Assignee:** –
**Dependencies:** US-2.1, US-2.2
**Blocking:** US-2.5

**Beschreibung:**
Als Systembetreiber möchte ich Text aus Dokumenten kosteneffizient extrahieren, damit nur bei schwer lesbaren Bildern teure Cloud-APIs (Azure) genutzt werden.

**Akzeptanzkriterien:**

- [ ] Nach erfolgreichem S3-Upload startet automatisch ein Hintergrundprozess zur Textextraktion
- [ ] **Stufe 1:** pypdf versucht Textextraktion
- [ ] **Stufe 2 (Fallback):** Wenn pypdf fehlschlägt oder weniger als 50 zusammenhängende Zeichen liefert → Azure Document Intelligence
- [ ] Extrahierter Rohtext wird im Speicher der aktuellen Fall-Session hinterlegt
- [ ] GET `/api/v1/cases/{case_id}/status` gibt Fortschritt zurück: `processing` | `completed` | `error`

**Implementierungs-Notizen:**

- Code-Path: `app/workers/ocr_worker.py`, `app/api/routes/cases.py` (GET /status)
- Komponenten: pypdf, azure-ai-formrecognizer SDK, FastAPI `BackgroundTasks`
- Fallback-Trigger: `len(extracted_text.strip()) < 50`
- Status im DB-Feld `documents.ocr_status` speichern (nicht nur im RAM)

---

### US-2.5: PII-Masking Engine (Datenschutz)

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-2.4
**Blocking:** US-2.6

**Beschreibung:**
Als Nutzer möchte ich, dass meine sensibelsten Bank- und Kontaktdaten (IBAN, E-Mail) geschwärzt werden, bevor eine KI sie analysiert.

**Akzeptanzkriterien:**

- [ ] Backend wendet Regex-Muster auf den frisch extrahierten Rohtext an
- [ ] **IBAN-Regel:** Alle deutschen IBANs (kompakt + mit Leerzeichen) → `***IBAN***`
- [ ] **E-Mail-Regel:** Alle E-Mail-Adressen → `***@***.***`
- [ ] Backend überschreibt Rohtext im Speicher mit maskiertem Text
- [ ] Originaldokument im S3-Bucket bleibt **strikt unangetastet**

**Implementierungs-Notizen:**

- Code-Path: `app/core/masking.py`
- IBAN-Regex: `r'DE\d{2}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{2}'`
- E-Mail-Regex: `r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'`
- Unit-Tests mit mind. 10 realen IBAN-/E-Mail-Varianten (inkl. Edge Cases mit Leerzeichen)
- Maskierten Text in eigenem DB-Feld speichern (`documents.masked_text`), Rohtext nie persistieren

---

### US-2.6: UX – Masking Preview & Vertrauensaufbau

**Status:** Backlog
**Aufwand:** 8 Stunden
**Assignee:** –
**Dependencies:** US-2.5
**Blocking:** –

**Beschreibung:**
Als Nutzer möchte ich in der Oberfläche sehen, dass meine Daten erfolgreich geschwärzt wurden, um Vertrauen in das Tool aufzubauen.

**Akzeptanzkriterien:**

- [ ] Sobald REST-Polling Status `completed` zurückgibt, zeigt Frontend Erfolgsmeldung: „Dokumente erfolgreich analysiert"
- [ ] UI blendet einen kurzen Text-Ausschnitt (Preview) des extrahierten Textes ein
- [ ] Geschwärzte Stellen (`***IBAN***`, `***@***.***`) werden grün hinterlegt dargestellt mit Tooltip: „Zu deiner Sicherheit vor der KI verborgen"
- [ ] Button „Weiter zur Fall-Analyse" triggert den LangGraph-Agenten (Epic 3)

**Implementierungs-Notizen:**

- Code-Path: Frontend: `components/MaskingPreview.tsx`
- Komponenten: Regex im Frontend zum Highlighting (`***...**`-Pattern erkennen und `<mark>`-Tag wrappen)
- Preview: max. 500 Zeichen des maskierten Textes anzeigen (mit „..." truncation)
- „Weiter"-Button: POST `/api/v1/cases/{case_id}/analyze` (Epic 3 Einstiegspunkt)

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
US-2.1 (S3 Storage Setup)
├─ Keine Dependencies
├─ Blocking für: US-2.2, US-2.3, US-2.4, US-2.5

US-2.2 (Datei-Upload & Compression)
├─ Abhängig von: US-2.1
├─ Blocking für: US-2.3, US-2.4

US-2.3 (QR-Code Magic Flow)
├─ Abhängig von: US-2.1, US-2.2
├─ Blocking für: –

US-2.4 (Async OCR-Worker)
├─ Abhängig von: US-2.1, US-2.2
├─ Blocking für: US-2.5

US-2.5 (PII-Masking Engine)
├─ Abhängig von: US-2.4
├─ Blocking für: US-2.6

US-2.6 (Masking Preview UX)
├─ Abhängig von: US-2.5
├─ Blocking für: Epic 3 (LangGraph-Agent)
```
