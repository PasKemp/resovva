## **📄 Epic 2: Document Ingestion & Privacy**

### **📖 Epic Summary**

Dieses Epic deckt den gesamten Prozess vom Nutzergerät bis zum sauberen, maschinenlesbaren Text ab. Nutzer können Dokumente (PDFs, Bilder) per PC oder via QR-Code-Scan direkt vom Smartphone hochladen. Die Dateien werden clientseitig komprimiert und sicher in einem S3-kompatiblen Storage (z. B. MinIO für lokale Entwicklung) abgelegt. Das Backend extrahiert den Text asynchron (mit einer Fallback-Logik von pypdf zu Azure) und schwärzt sensible Daten (IBAN, E-Mail) über harte Regex-Regeln. Das Originaldokument bleibt unangetastet als Beweismittelanhang für das finale PDF-Dossier erhalten.

### **📐 Architektur & Tech Notes**

* **Storage:** Implementierung via boto3 (AWS S3 SDK). Für die lokale Entwicklung läuft ein MinIO-Container im Docker-Setup. Kein Vendor-Lock-in.  
* **Async & Polling:** Der Upload speichert die Datei und triggert einen Hintergrund-Task (z. B. via FastAPI BackgroundTasks). Das Frontend fragt über REST-Polling den Status ab.  
* **OCR-Fallback:** Kostenlose Text-Extraktion hat Vorrang. Nur bei bildbasierten PDFs oder JPEGs springt die Azure Document Intelligence API ein.  
* **Datenschutz:** Regex-Masking läuft direkt nach der Textextraktion. Das LLM sieht ausschließlich den maskierten Text.

### ---

**🎫 Jira User Stories (In Implementierungsreihenfolge)**

#### **🗄️ \[US-2.1\] Setup: S3-kompatibler Storage Service**

**Story:** Als Entwickler muss ich eine S3-kompatible Speicherinfrastruktur aufsetzen, damit Uploads sicher, skalierbar und getrennt vom App-Container gespeichert werden (Vorbereitung für den Beweismittelanhang).

**Akzeptanzkriterien (ACs):**

* \[ \] Die lokale docker-compose.yml enthält einen MinIO-Service inkl. persistenter Volumes.  
* \[ \] Ein StorageService (Python-Klasse in app/infrastructure) ist implementiert und nutzt boto3.  
* \[ \] Der Service bietet Methoden zum Hochladen (upload\_file), Herunterladen (download\_file) und Löschen (delete\_file) von Dateien.  
* \[ \] Die S3-Credentials (Endpoint, Access Key, Secret Key, Bucket Name) werden flexibel über die .env-Datei gesteuert.

#### **📤 \[US-2.2\] Datei-Upload & Client-Side Compression**

**Story:** Als Nutzer möchte ich Rechnungen und Verträge als PDF oder Bild hochladen können, ohne dass große Dateien den Server überlasten.

**Akzeptanzkriterien (ACs):**

* \[ \] Das Frontend erlaubt den Upload von .pdf, .jpg, .jpeg und .png.  
* \[ \] **Client-Side Compression:** Bilder werden im Browser vor dem Upload automatisch komprimiert (z. B. max. 2000px Breite, Konvertierung zu JPEG, max. Qualität 80%).  
* \[ \] Ein hartes Dateigrößen-Limit von 10 MB pro Datei (nach Komprimierung) wird im Frontend und Backend forciert.  
* \[ \] Das Backend nimmt die Datei entgegen, generiert einen eindeutigen Dateinamen (UUID) und speichert sie über den StorageService im S3-Bucket unter dem Pfad case\_id/Dateiname.

#### **📱 \[US-2.3\] Cross-Device Upload (Der "QR-Code Magic Flow")**

**Story:** Als Nutzer am PC möchte ich Papierdokumente schnell mit meinem Smartphone abfotografieren und direkt in meinen Fall einfügen können, ohne mir die Bilder selbst mailen zu müssen.

**Akzeptanzkriterien (ACs):**

* \[ \] Das PC-Frontend bietet einen Button "Mit dem Handy scannen".  
* \[ \] Klick generiert im Backend ein kurzlebiges, sicheres Upload-Token (Gültigkeit: 15 Minuten) für die spezifische case\_id.  
* \[ \] Das PC-Frontend zeigt einen QR-Code an, der eine URL mit diesem Token enthält (z. B. resovva.de/mobile-upload?token=abc).  
* \[ \] Scannt der Nutzer den Code, öffnet sich eine mobile Web-Ansicht mit Kamera-Zugriff. Die gemachten Fotos werden (inkl. Client-Compression aus US-2.2) direkt an die API gesendet.  
* \[ \] Das PC-Frontend fragt im Hintergrund alle 2 Sekunden neue Dateien ab (Polling) und zeigt hochgeladene Handy-Fotos sofort an.

#### **⚙️ \[US-2.4\] Async OCR-Worker & Fallback-Logik**

**Story:** Als Systembetreiber möchte ich Text aus Dokumenten kosteneffizient extrahieren, damit nur bei schwer lesbaren Bildern teure Cloud-APIs (Azure) genutzt werden.

**Akzeptanzkriterien (ACs):**

* \[ \] Nach dem erfolgreichen Speichern (S3) startet ein Hintergrundprozess zur Textextraktion.  
* \[ \] **Stufe 1:** Das System versucht, den Text mit pypdf zu lesen.  
* \[ \] **Stufe 2 (Fallback):** Wenn pypdf fehlschlägt oder weniger als 50 zusammenhängende Zeichen findet (Indikator für einen Scan), wird das Dokument an Azure Document Intelligence gesendet.  
* \[ \] Das extrahierte Rohtext-Ergebnis wird vorläufig im Speicher der aktuellen Fall-Session hinterlegt.  
* \[ \] Die API bietet einen Endpunkt GET /api/v1/cases/{case\_id}/status, der dem Frontend den Fortschritt ("processing", "completed", "error") mitteilt.

#### **🕵️ \[US-2.5\] PII-Masking Engine (Datenschutz)**

**Story:** Als Nutzer möchte ich, dass meine sensibelsten Bank- und Kontaktdaten (IBAN, E-Mail) geschwärzt werden, bevor eine KI sie analysiert.

**Akzeptanzkriterien (ACs):**

* \[ \] Das Backend wendet Regex-basierte Suchmuster auf den gesamten, frisch extrahierten Rohtext an.  
* \[ \] **IBAN-Regel:** Alle deutschen IBANs (kompakt oder mit Leerzeichen) werden durch den String \*\*\*IBAN\*\*\* ersetzt.  
* \[ \] **E-Mail-Regel:** Alle E-Mail-Adressen werden durch \*\*\*@\*\*\*.\*\*\* ersetzt.  
* \[ \] Das Backend überschreibt den Rohtext im Speicher mit dem maskierten Text. *Das Originaldokument im S3-Bucket bleibt strikt unangetastet.*

#### **👀 \[US-2.6\] UX: Masking Preview & Vertrauensaufbau**

**Story:** Als Nutzer möchte ich in der Oberfläche sehen, dass meine Daten erfolgreich geschwärzt wurden, um Vertrauen in das Tool aufzubauen.

**Akzeptanzkriterien (ACs):**

* \[ \] Sobald das REST-Polling den Status "completed" zurückgibt, zeigt das Frontend eine Erfolgsmeldung ("Dokumente erfolgreich analysiert").  
* \[ \] Das UI blendet einen kurzen Ausschnitt (Preview) des extrahierten Textes ein.  
* \[ \] Geschwärzte Stellen (wie \*\*\*IBAN\*\*\*) werden farblich (z. B. grün hinterlegt) hervorgehoben, versehen mit einem Tooltip: "Zu deiner Sicherheit vor der KI verborgen."  
* \[ \] Es gibt einen Button "Weiter zur Fall-Analyse", der den LangGraph-Agenten für Epic 3 triggert.