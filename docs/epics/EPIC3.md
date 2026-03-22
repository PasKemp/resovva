## **🧠 Epic 3: AI Analysis & Extraction Engine**

### **📖 Epic Summary**

Dieses Epic implementiert den ersten Durchlauf des LangGraph-Agenten. Der maskierte Text aus Epic 2 wird vektorisiert (RAG) und in Qdrant gespeichert. Ein kosteneffizientes LLM (gpt-4o-mini) sucht gezielt nach Kern-Fakten (MaLo, Zählernummer, Beträge). Fehlen diese Daten, pausiert der Agent (Early Exit) und bittet den Nutzer um manuelle Eingabe oder einen weiteren Upload. Wurden Daten gefunden, ermittelt das System über die MaStR-API (oder KI-Fallback) den zuständigen Netzbetreiber. Am Ende präsentiert die UI dem Nutzer die gefundenen Fakten zur manuellen Bestätigung (Human-in-the-Loop), bevor der Fall weiterbearbeitet wird.

### **📐 Architektur & Tech Notes**

* **RAG Setup:** LangChain RecursiveCharacterTextSplitter (ca. 1000 Tokens pro Chunk) und OpenAI text-embedding-3-small. Speicherung in Qdrant.  
* **LLM-Modell:** Strikt gpt-4o-mini (oder Azure Equivalent) für Pydantic-basierte Struktur-Extraktion (ExtractedEntity), um die Kosten unter 0,05 € pro Fall zu halten.  
* **LangGraph State:** Nutzung von interrupt\_before oder Conditional Edges, um den Graphen zu pausieren. Der State wird via langgraph-checkpoint-postgres persistiert.

### ---

**🎫 Jira User Stories (In Implementierungsreihenfolge)**

#### **🧩 \[US-3.1\] RAG Foundation (Chunking & Embeddings)**

**Story:** Als Systembetreiber möchte ich große Dokumente in Vektoren umwandeln und in Qdrant speichern, damit die KI später effizient und kostengünstig nach spezifischen Informationen suchen kann.

**Akzeptanzkriterien (ACs):**

* \[ \] Eine Funktion nimmt den maskierten Rohtext aus Epic 2 und teilt ihn in sinnvolle Chunks (z.B. max. 1000 Zeichen, mit 100 Zeichen Overlap).  
* \[ \] Die Chunks werden via OpenAI API (text-embedding-3-small) in Vektoren umgewandelt.  
* \[ \] Die Vektoren werden zusammen mit den Metadaten (Case-ID, Document-ID) in einer Qdrant-Collection (resovva\_docs) gespeichert.

#### **🤖 \[US-3.2\] Core Entity Extraction (LLM)**

**Story:** Als Nutzer möchte ich, dass das System automatisch meine Zählernummer, Marktlokation (MaLo) und den Streitbetrag ausliest, damit ich diese nicht manuell abtippen muss.

**Akzeptanzkriterien (ACs):**

* \[ \] Der LangGraph-Node \_node\_extract führt eine RAG-Suche in Qdrant nach den relevantesten Textstellen für Zähler, MaLo und Beträge aus.  
* \[ \] Es wird strikt das LLM-Modell gpt-4o-mini verwendet, formatiert als with\_structured\_output(ExtractedEntity).  
* \[ \] Das Ergebnis der Extraktion wird in den LangGraph AgentState geschrieben. Findet die KI einen Wert nicht, wird das entsprechende Feld mit null befüllt.

#### **🛑 \[US-3.3\] Early Exit & Missing Data UI**

**Story:** Als Nutzer möchte ich sofort gewarnt werden, wenn essenzielle Daten (Zählernummer oder MaLo) fehlen, damit ich diese nachtragen kann, bevor das System Fehler macht.

**Akzeptanzkriterien (ACs):**

* \[ \] Eine Conditional Edge im LangGraph prüft nach der Extraktion: Sind meter\_number UND malo\_id gleich null?  
* \[ \] Wenn ja: Der Agent-Status wechselt auf WAITING\_FOR\_USER und der LangGraph-Run pausiert (Interrupt).  
* \[ \] Das Frontend pollt diesen Status und zeigt eine UI an: "Wir konnten keine Zählernummer finden."  
* \[ \] Die UI bietet zwei Optionen: 1\. Manuelle Eingabe über ein Formular. 2\. Button zum Hochladen eines weiteren Dokuments (z. B. der Jahresabrechnung).

#### **🔌 \[US-3.4\] MaStR-API Lookup & AI Fallback**

**Story:** Als Nutzer möchte ich, dass das System meinen exakten Netzbetreiber anhand der MaLo identifiziert, da ich oft nur meinen Stromanbieter kenne.

**Akzeptanzkriterien (ACs):**

* \[ \] Sobald eine valide MaLo vorliegt, macht das Backend einen HTTP-Request an die offizielle MaStR-API (mastr\_lookup\_tool).  
* \[ \] Findet die API den Netzbetreiber, wird dieser in den State geschrieben.  
* \[ \] **Fallback:** Ist die API offline oder liefert kein Ergebnis, macht das System einen gezielten RAG-Aufruf (gpt-4o-mini), um den Namen des Netzbetreibers aus dem Briefkopf der hochgeladenen Dokumente zu extrahieren.

#### **🙋‍♂️ \[US-3.5\] Human-in-the-Loop & Graph Resume**

**Story:** Als Nutzer möchte ich die von der KI erkannten Daten kontrollieren und korrigieren können, bevor das finale Dossier erstellt wird.

**Akzeptanzkriterien (ACs):**

* \[ \] Sobald die Extraktion (und der MaStR-Lookup) fertig sind, geht der Agent in den State WAITING\_FOR\_USER (Interrupt).  
* \[ \] Das Frontend zeigt ein übersichtliches Formular mit den extrahierten Daten (Zählernummer, MaLo, Betrag, Netzbetreiber).  
* \[ \] Der Nutzer kann die Felder editieren oder auf "Bestätigen & Weiter" klicken.  
* \[ \] Der Klick sendet einen POST-Request an api/v1/workflows/resume mit den finalen, bestätigten Daten.  
* \[ \] Der LangGraph überschreibt seinen internen State mit diesen User-Daten und weckt den Agenten auf, um mit Epic 4 fortzufahren.