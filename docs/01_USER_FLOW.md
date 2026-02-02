# 01. User Flow & System States

Der User durchläuft einen linearen Wizard: Upload → Analyse → Chronologie-Preview → ggf. weitere Dokumente → Bezahlung → Dossier-Download.

---

## Ablaufdiagramm

```mermaid
graph TD
    %% User Actions
    Start((Start / Landing)) --> Upload[Upload Documents<br/>PDF/Images/EML]

    %% System Backend Processes
    subgraph "Phase 1: Ingestion & Analysis"
        Upload --> OCR[OCR & Parsing Service]
        OCR --> Extraction[LLM Entity Extraction<br/>(Dates, Amounts, MaLo)]
        Extraction --> Chrono[Chronology Builder]
    end

    %% User Interaction
    Chrono --> Preview{Chronologie Preview<br/>'The Magic Moment'}

    Preview -- "Infos fehlen" --> GapLoop[User lädt weitere Docs hoch]
    GapLoop --> OCR

    Preview -- "Alles korrekt" --> Paywall[Stripe Checkout<br/>20€ Payment]

    %% Final Generation
    subgraph "Phase 2: Execution"
        Paywall --> DossierGen[LLM Dossier Writer]
        DossierGen --> PDFBuild[PDF Compilation]
    end

    PDFBuild --> Download((Download Final Dossier))
```

---

## Phasen im Überblick

| Phase            | Inhalt                                                                        |
| ---------------- | ----------------------------------------------------------------------------- |
| **Phase 1**      | Ingestion & Analysis: OCR → Entity Extraction → Chronology Builder            |
| **Entscheidung** | Chronologie-Preview: Infos fehlen → weitere Docs hochladen, sonst → Bezahlung |
| **Phase 2**      | Execution: Dossier-Generierung (LLM) → PDF-Kompilierung → Download            |
