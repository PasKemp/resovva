## ---

**📘 Epic 1: User Onboarding & Session Management**

### **📖 Epic Summary**

Das System bietet einen sicheren Zugang via E-Mail und Passwort. Nach der Authentifizierung landen die Nutzer in einem persönlichen Dashboard, in dem sie mehrere rechtliche Konflikte (Cases) parallel verwalten können. Mandantenfähigkeit (Tenant Isolation) stellt sicher, dass Nutzer nur ihre eigenen Daten sehen. Sensible Daten bleiben gespeichert, bis der Nutzer explizit eine Löschung anfordert (DSGVO Hard-Delete) oder die Inaktivitätsfrist abläuft.

### **📐 Architektur & Tech Notes für das Epic**

* **Passwort-Sicherheit:** Passwörter werden niemals im Klartext gespeichert. Nutzung von bcrypt oder passlib im FastAPI-Backend.  
* **Session-Management:** Stateful über JWTs (JSON Web Tokens), die in einem **Secure, HttpOnly-Cookie** gespeichert werden (Schutz vor XSS).  
* **Datenbank:** Einführung einer users-Tabelle (id, email, hashed\_password, created\_at) und Verknüpfung der bestehenden CaseState via user\_id als Foreign Key.  
* **Mail-Provider (für Reset-Mails):** Resend (kostenloses Kontingent reicht für MVP).

### ---

**🎫 Jira User Stories (In Implementierungsreihenfolge)**

#### **🛠️ \[US-1.1\] Setup: DB-Schema & Security Foundation (Backend Task)**

**Story:** Als Entwickler muss ich das Datenbankschema für Nutzerkonten und die grundlegende Kryptografie einrichten, bevor User sich registrieren können.

**Akzeptanzkriterien (ACs):**

* \[ \] Die Datenbank enthält eine Tabelle users (id, email \[unique\], hashed\_password, created\_at).  
* \[ \] Die Entität CaseState (bzw. die Tabelle cases) erhält einen Foreign Key user\_id.  
* \[ \] Eine Utility-Funktion zum Hashen von Passwörtern (hash\_password) und zur Verifikation (verify\_password) ist im Modul app/core/security.py implementiert.

#### **👤 \[US-1.2\] Registrierung (Sign Up)**

**Story:** Als neuer Nutzer möchte ich mir ein Konto mit E-Mail und Passwort erstellen, um meine Fälle dauerhaft und unkompliziert speichern zu können.

**Akzeptanzkriterien (ACs):**

* \[ \] Das UI bietet ein Formular mit Feldern für E-Mail, Passwort und Passwort-Bestätigung.  
* \[ \] **Passwort-Richtlinien:** Das Backend lehnt Passwörter ab, die kürzer als 8 Zeichen sind.  
* \[ \] **Rechtliches:** Das Formular enthält eine zwingend anzukreuzende Checkbox: "Ich akzeptiere die AGB und die Datenschutzerklärung." (Links hinterlegt).  
* \[ \] Das Backend speichert bei erfolgreicher Validierung den neuen User (mit gehashtem Passwort) in der DB.  
* \[ \] Versucht sich eine E-Mail zu registrieren, die schon existiert, wird eine generische Fehlermeldung geworfen ("E-Mail wird bereits verwendet"), um Fehler abzufangen.  
* \[ \] Nach der Registrierung wird der Nutzer direkt eingeloggt (Session-Cookie wird gesetzt) und ins leere Dashboard weitergeleitet.

#### **🔑 \[US-1.3\] Login & Session-Erstellung (Sign In)**

**Story:** Als bestehender Nutzer möchte ich mich mit E-Mail und Passwort einloggen, um auf meine gespeicherten Fälle zuzugreifen.

**Akzeptanzkriterien (ACs):**

* \[ \] Das UI bietet ein Login-Formular (E-Mail, Passwort).  
* \[ \] Das System prüft den Passwort-Hash gegen die Datenbank.  
* \[ \] Bei falschen Daten: Das System gibt eine neutrale Fehlermeldung aus ("E-Mail oder Passwort falsch") \-\> *Sicherheit gegen Account-Enumeration*.  
* \[ \] Bei Erfolg: Ein JWT-Token wird generiert und als **HttpOnly, Secure Cookie** an den Browser gesendet.  
* \[ \] **Brute-Force-Schutz:** Die Login-Route in FastAPI limitiert Anfragen pro IP (z.B. max. 5 fehlgeschlagene Versuche pro 15 Minuten).

#### **🛡️ \[US-1.4\] API-Security & Tenant Isolation**

**Story:** Als Systembetreiber muss ich sicherstellen, dass Nutzer über die API (FastAPI) ausschließlich auf ihre eigenen Fälle zugreifen können.

**Akzeptanzkriterien (ACs):**

* \[ \] Der Dependency-Injector Depends(get\_current\_user) in FastAPI extrahiert und verifiziert das Token aus dem Cookie bei jedem geschützten API-Call.  
* \[ \] Bei Abfragen eines Cases (z. B. GET /api/v1/workflows/{case\_id}) wird zwingend geprüft, ob die case\_id zur user\_id der aktuellen Session gehört.  
* \[ \] Schlägt die Prüfung fehl (fremder Case), wird ein 404 Not Found (nicht 403 Forbidden) zurückgegeben.

#### **🚪 \[US-1.5\] Logout & Session Expiration**

**Story:** Als Nutzer möchte ich mich aktiv abmelden können und nach längerer Inaktivität automatisch abgemeldet werden, um meine Daten zu schützen.

**Akzeptanzkriterien (ACs):**

* \[ \] Das Dashboard enthält einen deutlich sichtbaren "Abmelden"-Button.  
* \[ \] Klick auf "Abmelden" ruft einen Backend-Endpoint auf, der das HttpOnly-Cookie löscht/invalidiert.  
* \[ \] Der Nutzer wird nach dem Logout auf die Landingpage weitergeleitet.  
* \[ \] **Session Expiration:** Das JWT/Cookie hat eine maximale Lebensdauer von 7 Tagen. Danach verlangt das System einen erneuten Login.

#### **📊 \[US-1.6\] Multi-Case Dashboard**

**Story:** Als eingeloggter Nutzer möchte ich eine Übersicht meiner bestehenden Fälle sehen und einen neuen Fall starten können.

**Akzeptanzkriterien (ACs):**

* \[ \] Die Route /dashboard ruft alle Cases des eingeloggten Nutzers (user\_id) ab und stellt sie als Liste/Grid dar.  
* \[ \] Jeder Case zeigt Metadaten: Erstelldatum, Status (z.B. Draft, Analyzing) und, falls vorhanden, den Namen des Netzbetreibers/Anbieters.  
* \[ \] Es gibt einen Button "Neuen Fall starten".  
* \[ \] Klick auf den Button generiert eine neue case\_id im Backend (verknüpft mit dem User), speichert diesen in der DB und leitet den Nutzer zum Document-Upload-Flow (Epic 2\) weiter.

#### **🗑️ \[US-1.7\] Data Deletion (DSGVO Hard-Delete)**

**Story:** Als Nutzer möchte ich einen spezifischen Fall und alle zugehörigen Daten permanent löschen können.

**Akzeptanzkriterien (ACs):**

* \[ \] Jeder Case im Dashboard hat eine Option "Fall unwiderruflich löschen" (z.B. über ein Kontextmenü/Drei-Punkte-Menü).  
* \[ \] Ein Warn-Modal verlangt eine explizite Bestätigung ("Diese Aktion kann nicht rückgängig gemacht werden").  
* \[ \] Nach Bestätigung führt das Backend einen **Hard-Delete** aus:  
  * Metadaten und State aus Postgres löschen.  
  * Vektor-Embeddings aus Qdrant löschen.  
  * Physische PDF/Bilder aus dem Storage löschen.  
* \[ \] Das Dashboard lädt neu und der Fall ist verschwunden.

#### **✉️ \[US-1.8\] Passwort vergessen (Reset-Flow)**

**Story:** Als Nutzer, der sein Passwort vergessen hat, möchte ich dieses über einen sicheren Link an meine E-Mail-Adresse zurücksetzen können.

**Akzeptanzkriterien (ACs):**

* \[ \] Die Login-Seite hat einen Link "Passwort vergessen", der zu einem Eingabefeld für die E-Mail-Adresse führt.  
* \[ \] Das Backend generiert ein sicheres Reset-Token (Gültigkeit: 15 Minuten), speichert den Hash temporär in der DB und triggert den Mail-Provider (Resend).  
* \[ \] Die UI zeigt sofort eine Erfolgsmeldung ("Falls ein Account existiert, wurde eine E-Mail gesendet"), unabhängig davon, ob die E-Mail registriert ist.  
* \[ \] Klickt der Nutzer den Link in der E-Mail (/reset-password?token=...), kann er ein neues Passwort eingeben.  
* \[ \] Nach dem Speichern wird das alte Token invalidiert und das neue Passwort gehasht in die DB geschrieben.

---

Mit dieser Reihenfolge kann ein Entwickler (oder du) Ticket für Ticket abarbeiten, ohne in Abhängigkeitsprobleme zu laufen.

Wenn das für dich die perfekte Blaupause für dein erstes Epic ist, können wir genau nach diesem Muster mit **Epic 2: Document Ingestion & Privacy** (wo wir die Magie des PDF-Parsings und der Daten-Schwärzung spezifizieren) weitermachen\!