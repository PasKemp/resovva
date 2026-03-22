### **📡 API-Design & JSON-Verträge (v1)**

Alle Endpunkte liegen unter dem Präfix: https://api.resovva.de/api/v1

#### **1\. Auth & Session Management (Epic 1\)**

**POST /auth/register**

* **Zweck:** Legt einen neuen Nutzer an und setzt direkt das HttpOnly-Session-Cookie.  
* **Request (Body):**

JSON

{  
  "email": "max@mustermann.de",  
  "password": "SuperSecretPassword123\!",  
  "accepted\_terms": true  
}

* **Response (201 Created):**

JSON

{  
  "status": "success",  
  "user\_id": "usr\_9f8e7d6c",  
  "message": "Registrierung erfolgreich. Du bist eingeloggt."  
}

**POST /auth/login**

* **Zweck:** Prüft Credentials und setzt das HttpOnly-Cookie.  
* **Request (Body):**

JSON

{  
  "email": "max@mustermann.de",  
  "password": "SuperSecretPassword123\!"  
}

* **Response (200 OK):**

JSON

{  
  "status": "success",  
  "user\_id": "usr\_9f8e7d6c"  
}

#### **2\. Case Management (Dashboard)**

**GET /cases**

* **Zweck:** Lädt alle Fälle des eingeloggten Nutzers für das Dashboard.  
* **Request:** (Kein Body, Auth via Cookie)  
* **Response (200 OK):**

JSON

{  
  "cases": \[  
    {  
      "case\_id": "case\_1a2b3c",  
      "created\_at": "2026-03-20T14:30:00Z",  
      "status": "WAITING\_FOR\_USER",  
      "network\_operator": "E.ON Energie Deutschland",  
      "document\_count": 3  
    },  
    {  
      "case\_id": "case\_9x8y7z",  
      "created\_at": "2026-03-01T09:15:00Z",  
      "status": "COMPLETED",  
      "network\_operator": "Vattenfall",  
      "document\_count": 5  
    }  
  \]  
}

**POST /cases**

* **Zweck:** Erstellt einen neuen, leeren Fall (Klick auf "+ Neuen Fall starten").  
* **Request:** (Kein Body)  
* **Response (201 Created):**

JSON

{  
  "case\_id": "case\_new456",  
  "status": "DRAFT",  
  "message": "Neuer Fall erfolgreich angelegt."  
}

#### **3\. Document Ingestion (Epic 2\)**

**POST /cases/{case\_id}/documents**

* **Zweck:** Upload von PDFs oder Bildern (PC oder via Handy-QR-Code).  
* **Request:** multipart/form-data (Datei-Upload)  
* **Response (202 Accepted):**

JSON

{  
  "document\_id": "doc\_889900",  
  "filename": "Jahresabrechnung\_2025.pdf",  
  "status": "processing",  
  "message": "Datei hochgeladen. OCR und Masking gestartet."  
}

**GET /cases/{case\_id}/status** (Polling-Endpunkt für den Stepper)

* **Zweck:** Das Frontend fragt alle 2 Sekunden: "Ist die KI schon fertig?"  
* **Response (200 OK):**

JSON

{  
  "case\_id": "case\_1a2b3c",  
  "current\_step": "extract",  
  "is\_processing": false,  
  "extracted\_preview": "Sehr geehrter Herr Mustermann, wir buchen 120,00 EUR von \*\*\*IBAN\*\*\* ab..."  
}

#### **4\. AI Extraction & Human-in-the-Loop (Epic 3\)**

**GET /cases/{case\_id}/extraction**

* **Zweck:** Lädt die von der KI (gpt-4o-mini) erkannten Stammdaten in das Bestätigungs-Formular der UI.  
* **Response (200 OK):**

JSON

{  
  "extracted\_entities": {  
    "malo\_id": "11223344556677",  
    "meter\_number": "1EBZ012345",  
    "amount\_disputed": 120.50,  
    "network\_operator": "Netze BW GmbH"  
  },  
  "confidence\_warnings": \["Netzbetreiber via KI-Fallback ermittelt. Bitte prüfen."\]  
}

**PUT /cases/{case\_id}/extraction**

* **Zweck:** Der Nutzer klickt auf "Bestätigen & Weiter". Die Daten werden gespeichert und der LangGraph-Agent wird fortgesetzt (resume).  
* **Request (Body):** (Das Frontend sendet die ggf. korrigierten Daten zurück)

JSON

{  
  "malo\_id": "11223344556677",  
  "meter\_number": "1EBZ012345",  
  "amount\_disputed": 150.00,   
  "network\_operator": "Netze BW GmbH"  
}

* **Response (200 OK):** {"status": "success", "next\_step": "chronology"}

#### **5\. Der Rote Faden / Chronologie (Epic 4\)**

**GET /cases/{case\_id}/timeline**

* **Zweck:** Lädt die fertige Chronologie (und gefundene Lücken) für die UI-Tabelle.  
* **Response (200 OK):**

JSON

{  
  "timeline": \[  
    {  
      "event\_id": "evt\_1",  
      "date": "2025-01-15",  
      "description": "Jahresabrechnung 2024 erhalten.",  
      "source\_doc\_id": "doc\_889900",  
      "source\_type": "ai",  
      "is\_gap": false  
    },  
    {  
      "event\_id": "evt\_2",  
      "date": "2025-02-10",  
      "description": "Vermutlich fehlendes Dokument: Mahnung oder Zahlungserinnerung.",  
      "source\_doc\_id": null,  
      "source\_type": "ai",  
      "is\_gap": true  
    }  
  \]  
}

**POST /cases/{case\_id}/timeline**

* **Zweck:** Der Nutzer fügt ein eigenes Ereignis (z. B. Telefonat) manuell hinzu.  
* **Request (Body):**

JSON

{  
  "date": "2025-02-05",  
  "description": "Telefonat mit Kundenservice. Mir wurde eine Gutschrift zugesichert."  
}

* **Response (201 Created):**

JSON

{  
  "event\_id": "evt\_3",  
  "status": "success",  
  "source\_type": "user"  
}

#### **6\. Checkout & Dossier (Epic 5 & 6\)**

**POST /cases/{case\_id}/checkout**

* **Zweck:** Der Nutzer akzeptiert den Widerrufs-Verzicht und klickt auf "Kostenpflichtig bestellen".  
* **Request (Body):**

JSON

{  
  "waived\_withdrawal\_right": true  
}

* **Response (200 OK):**

JSON

{  
  "checkout\_url": "https://checkout.stripe.com/pay/cs\_test\_a1b2c3..."  
}

**GET /cases/{case\_id}/download**

* **Zweck:** Holt den sicheren Download-Link für das finale PDF-Dossier, nachdem Stripe die Zahlung bestätigt hat (Status COMPLETED).  
* **Response (200 OK):**

JSON

{  
  "download\_url": "https://minio.resovva.local/dossiers/case\_1a2b3c\_master.pdf?X-Amz-Signature=...",  
  "expires\_in\_seconds": 300  
}  
