## **📄 Epic 6: Dossier Generation & Export**

### **📖 Epic Summary**

In diesem finalen Schritt wird das Endprodukt erzeugt, für das der Nutzer bezahlt hat. Sobald die Zahlung via Stripe Webhook bestätigt ist, startet ein asynchroner Hintergrundprozess. Das System nutzt juristisch geprüfte Text-Templates (Jinja2/HTML), fügt die vom Nutzer bestätigten Stammdaten sowie die Chronologie ein und rendert ein Deckblatt und ein Anschreiben. Anschließend werden alle Original-Uploads aus dem S3-Speicher geladen (Bilder werden zu PDFs konvertiert), oben rechts mit einem digitalen Stempel ("Anlage 1", "Anlage 2") versehen und zu einem einzigen, großen Master-PDF zusammengefügt. Der Nutzer erhält eine Benachrichtigung per Mail und kann das PDF sicher im Dashboard herunterladen.

### **📐 Architektur & Tech Notes**

* **Template Engine:** Jinja2 (HTML/CSS), um das Layout flexibel und einfach anpassbar zu halten.  
* **PDF-Rendering:** WeasyPrint wandelt das HTML/CSS sauber in ein PDF um.  
* **Merging & Stamping:** pypdf (bereits im Projekt vorhanden) oder PyMuPDF werden genutzt, um die Anlagen zu stempeln und mit dem Haupt-PDF zu verschmelzen. Bilder (aus Epic 2\) werden vorher z.B. via Pillow (PIL) in PDFs umgewandelt.  
* **Zustellung:** Versand einer Benachrichtigungs-Mail via Resend. Download erfolgt über eine temporäre, signierte S3-URL (Presigned URL) hinter der Authentifizierungsschicht (FastAPI Depends(get\_current\_user)).

### ---

**🎫 Jira User Stories (In Implementierungsreihenfolge)**

#### **📝 \[US-6.1\] Setup: Template Engine & Basis-Layout**

**Story:** Als Legal/Content Manager möchte ich HTML-Templates für das Dossier nutzen, um rechtliche Textbausteine schnell und ohne Programmierkenntnisse anpassen zu können.

**Akzeptanzkriterien (ACs):**

* \[ \] Integration von Jinja2 in das FastAPI-Projekt (Ordner: app/templates).  
* \[ \] Erstellung eines Basis-HTML/CSS-Templates für das Dossier (Kopfzeile mit Logo, Briefkopf, Datum, saubere Typografie).  
* \[ \] Das Template enthält Variablen-Platzhalter für: Absender (Nutzer), Empfänger (Netzbetreiber), Datum, Zählernummer, MaLo, Betrag und die gerenderte Chronologie (als HTML-Tabelle oder Liste).

#### **🖨️ \[US-6.2\] PDF-Rendering (WeasyPrint)**

**Story:** Als Systembetreiber möchte ich die mit Daten befüllten HTML-Templates in ein professionelles, unveränderbares PDF-Format umwandeln.

**Akzeptanzkriterien (ACs):**

* \[ \] Integration von WeasyPrint als PDF-Generator.  
* \[ \] Ein Service DossierGenerator nimmt den aktuellen CaseState (aus der Postgres DB), füllt das Jinja2-Template und generiert das "Haupt-PDF" (Anschreiben \+ Chronologie) im Arbeitsspeicher.  
* \[ \] Seitenumbrüche innerhalb der Chronologie-Tabelle werden sauber gerendert (CSS page-break-inside: avoid).

#### **📎 \[US-6.3\] Evidence Compiler (Bilder wandeln, Stempeln & Mergen)**

**Story:** Als Nutzer möchte ich, dass alle meine hochgeladenen Original-Belege automatisch mit "Anlage X" gestempelt und an mein Anschreiben angehängt werden, damit ich nur eine einzige Datei verschicken muss.

**Akzeptanzkriterien (ACs):**

* \[ \] Ein Background-Task lädt alle zum Fall gehörenden Original-Dateien aus dem S3-Speicher (StorageService).  
* \[ \] **Bild-Konvertierung:** Uploads vom Typ .jpg und .png werden in ein A4-PDF-Format konvertiert.  
* \[ \] **Stempeln:** Jedes Anlage-Dokument erhält in der rechten oberen Ecke einen digitalen Text-Stempel (z. B. roter Text: "Anlage 1", "Anlage 2", korrespondierend zur Referenz in der Chronologie).  
* \[ \] **Merging:** Das Haupt-PDF aus US-6.2 und alle gestempelten Anlagen werden via pypdf zu einer einzigen Datei (dossier\_master.pdf) zusammengefügt und wieder im S3 gespeichert.

#### **⚙️ \[US-6.4\] Asynchroner Workflow & Status-Updates**

**Story:** Als Nutzer möchte ich nach der Zahlung sehen, dass mein Dossier gerade generiert wird, da dieser komplexe Prozess einige Sekunden dauern kann.

**Akzeptanzkriterien (ACs):**

* \[ \] Der erfolgreiche Stripe-Webhook aus Epic 5 ändert den Case-Status auf GENERATING\_DOSSIER und triggert den PDF-Erstellungs-Task (US-6.1 bis 6.3) im Hintergrund.  
* \[ \] Das Frontend pollt den Status (GET /api/v1/cases/{case\_id}).  
* \[ \] Schlägt die Generierung fehl, wird der Status auf ERROR\_GENERATION gesetzt (mit Option für Admins/Support, es neu anzustoßen).  
* \[ \] Bei Erfolg wechselt der Status auf COMPLETED.

#### **✉️ \[US-6.5\] Zustellung & Sicherer Download**

**Story:** Als Nutzer möchte ich per E-Mail informiert werden, sobald mein fertiges Dossier bereitsteht, und es sicher in meinem Konto herunterladen können.

**Akzeptanzkriterien (ACs):**

* \[ \] Wechselt der Status auf COMPLETED, triggert das Backend eine E-Mail (via Resend) an den Nutzer: *"Dein Resovva-Dossier ist fertig. Klicke hier, um es in deinem Dashboard herunterzuladen."*  
* \[ \] Der Link führt zu /dashboard/case/{case\_id} (erfordert Login).  
* \[ \] Im Dashboard gibt es einen prominenten Button "Dossier herunterladen".  
* \[ \] Klick auf den Button ruft einen geschützten API-Endpoint GET /api/v1/cases/{case\_id}/download auf.  
* \[ \] Dieser Endpoint generiert eine auf 5 Minuten befristete **Presigned S3 URL** und leitet den Browser zum Download weiter (sodass keine öffentlichen S3-Links existieren).