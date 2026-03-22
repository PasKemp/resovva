## **🧵 Epic 4: "Der Rote Faden" (Chronology & Gap Analysis)**

### **📖 Epic Summary**

Dieses Epic transformiert unstrukturierte Falldaten in eine präzise, juristisch verwertbare Chronologie. Das System nutzt ein Map-Reduce-Verfahren mit LLMs, um Ereignisse (sowohl aufgedruckte Belegdaten als auch im Text referenzierte Geschehnisse wie Telefonate) aus den Dokumenten zu extrahieren und zeitlich zu ordnen. Eine KI-gestützte "Gap Analysis" deckt Logiklücken auf (fehlende Rechnungen/Mahnungen) und weist den Nutzer als "Soft Blocker" darauf hin. Der Nutzer hat in der UI die volle Kontrolle: Er kann die KI-Timeline bearbeiten, löschen, eigene Ereignisse ohne Beleg hinzufügen oder iterativ fehlende Dokumente nachreichen, woraufhin sich die Timeline intelligent aktualisiert.

### **📐 Architektur & Tech Notes**

* **LLM Pipeline (Map-Reduce):** \* *Map:* gpt-4o-mini pro Dokument zur Extraktion lokaler Events (Metadaten-Generierung).  
  * *Reduce:* gpt-4o zur Aggregation, Deduplizierung und Lücken-Erkennung.  
* **State Management:** Der LangGraph Checkpointer (PostgresSaver) ist hier essenziell. Wenn der Nutzer manuell ein Event hinzufügt oder editiert, wird dies im State mit einem Flag source: user markiert. Löst ein iterativer Upload einen Re-Run aus, instruiert der Prompt die KI, source: user Events unangetastet zu lassen.  
* **Wording:** Verzicht auf strenges "Amtsdeutsch" bei Lücken. Stattdessen nutzerfreundliche Begriffe wie "Beleg fehlt" oder "Eigene Angabe".

### ---

**🎫 Jira User Stories (In Implementierungsreihenfolge)**

#### **🗺️ \[US-4.1\] Event-Extraktion pro Dokument (Map-Phase)**

**Story:** Als Systembetreiber möchte ich jedes Dokument einzeln auf Ereignisse scannen, um eine saubere Datenbasis für die Chronologie zu schaffen, ohne teure LLMs zu verschwenden.

**Akzeptanzkriterien (ACs):**

* \[ \] Ein neuer LangGraph-Node (\_node\_extract\_events) verarbeitet jedes hochgeladene Dokument einzeln.  
* \[ \] Der Node nutzt gpt-4o-mini mit strukturiertem Output (Pydantic-Liste von ChronologyEvent: Datum, Beschreibung, Quelle).  
* \[ \] Die KI ist instruiert, sowohl das Erstellungsdatum des Dokuments als auch referenzierte Ereignisse (z.B. "Wie am 12.04. besprochen") zu extrahieren.  
* \[ \] Die extrahierten Event-Listen werden als Zwischenschritt im AgentState gespeichert.

#### **🔗 \[US-4.2\] Master-Chronologie & Gap Analysis (Reduce-Phase)**

**Story:** Als Nutzer möchte ich, dass das System alle meine Dokumente in eine logische, chronologische Reihenfolge bringt und mich auf fehlende Unterlagen hinweist.

**Akzeptanzkriterien (ACs):**

* \[ \] Ein LangGraph-Node (\_node\_build\_master\_timeline) nimmt alle Event-Listen aus US-4.1 und übergibt sie an gpt-4o.  
* \[ \] Die KI dedupliziert überschneidende Ereignisse und sortiert sie chronologisch (ältester Eintrag zuerst).  
* \[ \] **Gap Analysis:** Die KI prüft auf logische Brüche (z.B. Mahnung verweist auf Rechnung, die nicht in den Events existiert).  
* \[ \] Erkannte Lücken werden als spezielle Einträge in die Chronologie eingefügt (z.B. Flag is\_gap: true, Beschreibung: "Vermutlich fehlendes Dokument: Rechnung vom 01.03.").

#### **🖥️ \[US-4.3\] UI: Der interaktive "Rote Faden"**

**Story:** Als Nutzer möchte ich die von der KI erstellte Chronologie sehen, prüfen und bearbeiten können, da nur ich die volle Wahrheit über meinen Fall kenne.

**Akzeptanzkriterien (ACs):**

* \[ \] Das Frontend pollt den Status und zeigt bei Abschluss die generierte Chronologie als visuelle Zeitstrahl-Komponente oder Tabelle an.  
* \[ \] Jeder KI-generierte Eintrag hat ein Kontextmenü (Drei Punkte) mit den Optionen "Bearbeiten" und "Löschen".  
* \[ \] Änderungen des Nutzers senden einen API-Call (PUT /api/v1/cases/{case\_id}/timeline), der den Graph-State aktualisiert und das Event als source: user markiert.  
* \[ \] Lücken (Gaps) werden visuell hervorgehoben (z.B. gelbes Warn-Icon: "Hier fehlt uns ein Beleg. Du kannst ihn nachreichen oder ignorieren.").

#### **✍️ \[US-4.4\] UI: Manuelle Ereignisse hinzufügen (ohne Beleg)**

**Story:** Als Nutzer möchte ich wichtige Ereignisse (z.B. Telefonate, Haustürgespräche) manuell in die Chronologie eintragen können, auch wenn ich kein Papierdokument dafür habe.

**Akzeptanzkriterien (ACs):**

* \[ \] Die Chronologie-UI bietet einen Button "Ereignis hinzufügen".  
* \[ \] Ein Modal öffnet sich mit den Pflichtfeldern: Datum (Datepicker) und Beschreibung (Text).  
* \[ \] Nach dem Speichern wird das Ereignis chronologisch korrekt in die Ansicht einsortiert.  
* \[ \] Im finalen Daten-State wird dieses Ereignis als "Eigene Angabe (ohne Beleg)" markiert, um juristische Transparenz im Dossier zu wahren.

#### **🔄 \[US-4.5\] Die "Zurück-Schleife" (Iterativer Upload)**

**Story:** Als Nutzer möchte ich, wenn das System mich auf eine Lücke hinweist, das fehlende Dokument hochladen können, woraufhin sich die Chronologie automatisch aktualisiert.

**Akzeptanzkriterien (ACs):**

* \[ \] Die UI bietet bei erkannten Gaps einen Button "Fehlendes Dokument hochladen".  
* \[ \] Ein Klick öffnet den Upload-Flow aus Epic 2 (inklusive QR-Code-Option fürs Handy).  
* \[ \] Sobald das neue Dokument verarbeitet ist (OCR & Masking), wird der LangGraph-Agent an der richtigen Stelle wieder aufgeweckt (resume).  
* \[ \] Der Agent führt die Map-Reduce-Pipeline (US-4.1 & 4.2) **nur für das neue Dokument** aus und webt die neuen Erkenntnisse in die bestehende Master-Chronologie ein.  
* \[ \] **Kritisch:** Bereits vom Nutzer bearbeitete, gelöschte oder manuell hinzugefügte Events (source: user) dürfen durch diesen Re-Run **nicht** überschrieben oder gelöscht werden\!