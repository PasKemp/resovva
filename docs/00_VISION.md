# 🚀 Product Vision: Resovva.de

**"Waffengleichheit für Verbraucher im Energie-Dschungel."**

---

## 1. Vision & Mission

**Die Vision:** Niemand sollte auf sein Recht verzichten müssen, nur weil der Papierkram zu kompliziert, die Konzerne zu groß oder der Streitwert für einen Anwalt zu gering ist.
**Die Mission:** Resovva.de ist ein intelligenter Fall-Assistent (LegalTech), der Endverbrauchern hilft, das Chaos bei Streitigkeiten mit Stromanbietern und Netzbetreibern zu entwirren. Wir demokratisieren den Zugang zum Recht (_Access to Justice_), indem wir Technologie nutzen, um unstrukturierte Zettelwirtschaft in unschlagbare juristische Argumentationen zu verwandeln.

## 2. Das Problem

Der deutsche Energiemarkt ist hochgradig fehleranfällig und bürokratisch (Abrechnungsfehler, Probleme bei PV-Anlagen, Wechsel-Chaos).

- **Überforderung:** Verbraucher scheitern an der Strukturierung ihrer eigenen Belege, Mahnungen und Verträge.
- **Kostenfalle:** Für einen Streitwert von 200 € bis 500 € lohnt sich kein Anwalt. Verbraucherzentralen sind oft überlastet.
- **Informationsasymmetrie:** Energiekonzerne nutzen hochautomatisierte Systeme, während der Verbraucher mit ausgedruckten E-Mails und Notizzetteln kämpft.

## 3. Die Lösung & Core USP

Resovva.de verkauft **keine Rechtsberatung** (RDG-konform), sondern **Ordnung und Struktur**.
Der Nutzer lädt seine Dokumente hoch, und unser LangGraph-Agent erledigt den Rest:

1. **Fakten-Extraktion:** Identifikation von Zählernummern, Beträgen und Marktlokationen (inkl. MaStR-API Abgleich).
2. **Der Rote Faden:** Erstellung einer wasserdichten, chronologischen Beweishistorie aus allen hochgeladenen Dokumenten.
3. **Gap Analysis:** Die KI erkennt Logiklücken ("Hier wird eine Mahnung erwähnt, die nie hochgeladen wurde") und bittet den Nutzer um Ergänzung.
4. **Das finale Dossier:** Generierung eines professionellen PDF-Beschwerdeschreibens inklusive gestempelter Beweismittelanlagen ("Anlage 1"), bereit für die Schlichtungsstelle Energie oder den Anwalt.

## 4. Zielgruppe & Geschäftsmodell

- **Zielgruppe:** B2C. Privatpersonen und Kleinunternehmer in Deutschland mit anhaltenden Konflikten im Energiesektor.
- **Monetarisierung:** Fair und transparent. **20,00 € pro Fall** (Einmalzahlung via Stripe). Keine Abo-Fallen.
- **Value Proposition:** Der Nutzer erlebt den Wert ("Aha-Moment" in der Chronologie-Vorschau) kostenlos. Bezahlt wird erst, wenn das finale PDF generiert werden soll.

## 5. Produkt-Leitprinzipien

1. **Privacy-by-Design:** Sensible Daten (IBAN, E-Mails) werden lokal maskiert (Regex), bevor sie jemals ein Cloud-LLM erreichen. Vollständige Löschung auf Knopfdruck.
2. **Human-in-the-Loop:** Die KI macht die Schwerstarbeit, aber der Mensch hat das letzte Wort. Alle KI-Erkenntnisse müssen vom Nutzer bestätigt, editiert oder ergänzt werden können.
3. **Frictionless UX:** Egal ob am PC oder Smartphone. Dokumente können via QR-Code-Scan nahtlos zwischen Geräten in den Fall geladen werden.
4. **Kostenkontrolle (Unit Economics):** Intelligentes "Map-Reduce"-Verfahren bei LLMs. Günstige Modelle (`gpt-4o-mini`) für die Massenextraktion, starke Modelle (`gpt-4o`) nur für die logische Schlussfolgerung.

## 6. High-Level Architektur

- **Backend:** Python 3.12, FastAPI.
- **AI Orchestration:** LangGraph (Stateful Agents mit Postgres Checkpointer) & LangChain.
- **Datenhaltung:** PostgreSQL (Nutzer & State), S3/MinIO (Dokumentenspeicher, kein Vendor-Lock-in), Qdrant (Vektor-DB).
- **Infrastruktur:** Dockerisiert, bereit für Kubernetes, CI/CD via Jenkins.
- **Integrierte Services:** Stripe (Payment), Resend (Transactional Mails), offizielle MaStR-API (Netzbetreiber-Ermittlung).
