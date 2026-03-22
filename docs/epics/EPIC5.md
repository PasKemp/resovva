## **💳 Epic 5: Checkout & Monetization (Die Paywall)**

### **📖 Epic Summary**

Nachdem der Nutzer den "Roten Faden" (Chronologie) seines Falles kontrolliert und bestätigt hat, greift die Monetarisierungs-Phase. Das System präsentiert eine Zusammenfassung des Mehrwerts und fordert eine Einmalzahlung von 20,00 € (Pay-per-Case). Die Zahlungsabwicklung, inklusive Rabattcodes (Promo-Codes) und automatischer Rechnungsstellung, wird komplett über Stripe Checkout abgewickelt. Um rechtlich auf der sicheren Seite zu sein, verzichtet der Nutzer explizit auf sein 14-tägiges Widerrufsrecht für digitale Güter. Die Freischaltung des Falls für die finale Dossier-Generierung (Epic 6\) erfolgt asynchron, sicher und manipulationssicher via Stripe Webhooks.

### **📐 Architektur & Tech Notes**

* **Zahlungsanbieter:** Stripe Checkout API (Hosted Checkout Page).  
* **Tracking & Security:** Bei der Erstellung der Stripe-Session wird die case\_id als client\_reference\_id (oder in den metadata) mitgegeben.  
* **Webhook-Sicherheit:** Der FastAPI-Endpoint für den Webhook MUSS die Stripe-Signatur (stripe-signature Header) mit dem Webhook-Secret verifizieren, um zu verhindern, dass jemand Fake-Zahlungen an die API sendet.  
* **Status-Modell:** Der CaseStatus wechselt von ANALYZING/WAITING\_FOR\_USER zu PAYMENT\_PENDING (wenn der Checkout gestartet wird) und schließlich zu PAID (durch den Webhook).

### ---

**🎫 Jira User Stories (In Implementierungsreihenfolge)**

#### **⚙️ \[US-5.1\] Setup: Stripe Checkout Session (Backend)**

**Story:** Als Entwickler muss ich eine Schnittstelle zu Stripe bauen, die eine sichere Bezahlseite für einen spezifischen Fall generiert, damit der Nutzer dort seine Zahlungsdaten eingeben kann.

**Akzeptanzkriterien (ACs):**

* \[ \] Die API bietet einen Endpoint POST /api/v1/cases/{case\_id}/checkout.  
* \[ \] Das Backend ruft die Stripe API auf und erstellt eine checkout.session für ein Einmalprodukt (20,00 €).  
* \[ \] Die case\_id und user\_id werden zwingend in den metadata oder als client\_reference\_id der Session gespeichert.  
* \[ \] Stripe wird so konfiguriert, dass **Promo-Codes** (Rabatte) auf der Bezahlseite vom Nutzer eingegeben werden dürfen (allow\_promotion\_codes: true).  
* \[ \] Die API gibt die checkout\_url an das Frontend zurück, leitet den Nutzer aber noch nicht weiter. Der Case-Status wechselt auf PAYMENT\_PENDING.

#### **🪝 \[US-5.2\] Webhook-Handler für Zahlungsbestätigung (Backend)**

**Story:** Als Systembetreiber muss mein Server verlässlich mitbekommen, wenn eine Zahlung bei Stripe erfolgreich war, um den Fall manipulationssicher freizuschalten.

**Akzeptanzkriterien (ACs):**

* \[ \] Die API bietet einen Endpoint POST /api/v1/webhooks/stripe.  
* \[ \] **Security:** Der Endpoint verifiziert die Herkunft des Requests anhand des Stripe-Webhook-Secrets. (Ungültige Signaturen werfen einen 400 Error).  
* \[ \] Der Endpoint lauscht auf das Event checkout.session.completed.  
* \[ \] Bei Empfang des Events liest das Backend die case\_id aus den Metadaten aus und aktualisiert den Status des Falls in der Datenbank auf PAID.  
* \[ \] (Optional/Bonus): Loggen der Stripe-Transaktions-ID (payment\_intent) am Case für spätere Buchhaltungs-Referenzen.

#### **⚖️ \[US-5.3\] Paywall UI & Widerrufs-Verzicht (Frontend)**

**Story:** Als Nutzer möchte ich klar verstehen, wofür ich 20€ bezahle, und ich muss rechtlich bindend dem sofortigen Start der Dienstleistung zustimmen.

**Akzeptanzkriterien (ACs):**

* \[ \] Nach Bestätigung der Chronologie (Epic 4\) landet der Nutzer auf der Paywall-Seite.  
* \[ \] Die UI zeigt eine wertorientierte Zusammenfassung: "Deine Chronologie ist fertig. Lass uns jetzt dein finales, juristisches Dossier generieren. Preis: 20,00 €."  
* \[ \] **Abmahn-Schutz:** Es gibt eine zwingende Checkbox (nicht vorausgewählt\!): *"Ich verlange ausdrücklich, dass mit der Ausführung des Vertrags vor Ablauf der Widerrufsfrist begonnen wird. Mir ist bekannt, dass ich mit vollständiger Vertragserfüllung mein Widerrufsrecht verliere."*  
* \[ \] Der Button "Kostenpflichtig bestellen" ist erst klickbar, wenn die Checkbox aktiviert ist.  
* \[ \] Klick triggert den Endpoint aus US-5.1 und leitet den Nutzer auf die Stripe-URL weiter.

#### **🔄 \[US-5.4\] Abgebrochene Zahlungen & Dashboard-Retry**

**Story:** Als Nutzer, der den Bezahlvorgang versehentlich abgebrochen hat, möchte ich die Zahlung später aus meinem Dashboard heraus nachholen können, ohne den Fall neu anlegen zu müssen.

**Akzeptanzkriterien (ACs):**

* \[ \] Leitet Stripe den Nutzer nach einem Abbruch (Cancel-URL) zurück, landet er im Dashboard.  
* \[ \] Im Dashboard hat der Fall den Status "Zahlung ausstehend" (PAYMENT\_PENDING).  
* \[ \] Es gibt einen primären Button "Zahlung abschließen".  
* \[ \] Klick auf den Button generiert eine komplett **neue** Stripe-Session (erneuter Aufruf von US-5.1) und leitet den Nutzer wieder zu Stripe.

#### **🧾 \[US-5.5\] Automatisierte Rechnungsstellung (Stripe Config)**

**Story:** Als Systembetreiber möchte ich keinen manuellen Aufwand mit Rechnungen haben, daher soll Stripe nach erfolgreicher Zahlung automatisch eine korrekte PDF-Rechnung an den Kunden schicken.

**Akzeptanzkriterien (ACs):**

* \[ \] *Hinweis: Dies ist primär eine Konfigurationsaufgabe im Stripe Dashboard, kein Code.*  
* \[ \] Im Stripe Dashboard ist die automatische Rechnungserstellung ("Invoicing") aktiviert.  
* \[ \] Die Rechnungen enthalten das Resovva-Logo, die Firmenanschrift und weisen die deutsche Mehrwertsteuer (19%) korrekt aus.  
* \[ \] Der Kunde erhält die Rechnung nach dem Event checkout.session.completed automatisch per E-Mail von Stripe.