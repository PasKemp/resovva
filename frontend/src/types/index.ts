// ─────────────────────────────────────────────────────────────────────────────
// Shared Types
// ─────────────────────────────────────────────────────────────────────────────

export type Page =
  | "landing"
  | "login"
  | "dashboard"
  | "case"
  | "dossier"
  | "preise"
  | "hilfe"
  | "reset-password"
  | "mobile-upload"
  | "profile"
  | "complete-profile";

// ── Domain models ─────────────────────────────────────────────────────────────

/** Backend-Status-Werte (1:1 mit dem DB-Enum) */
export type CaseStatusApi =
  | "DRAFT"
  | "WAITING_FOR_USER"
  | "BUILDING_TIMELINE"
  | "TIMELINE_READY"
  | "PAYMENT_PENDING"
  | "PAID"
  | "GENERATING_DOSSIER"
  | "ERROR_GENERATION"
  | "COMPLETED";

/** Deutsche Anzeigebezeichnungen für das UI */
export type CaseStatus = "Entwurf" | "Wartet auf Zahlung" | "Zahlung ausstehend" | "Abgeschlossen";

/** API-Response-Format von GET /cases */
export interface ApiCase {
  case_id: string;
  created_at: string;
  status: CaseStatusApi;
  network_operator: string | null;
  opponent_category: string | null;
  opponent_name: string | null;
  document_count: number;
}

/** Frontend-Darstellung eines Falls (nach Mapping aus ApiCase) */
export interface Case {
  apiId: string;       // vollständige UUID für API-Calls (z.B. löschen)
  id: string;          // Kurzform für UI-Anzeige (letzte 6 Zeichen)
  date: string;
  operator: string;
  status: CaseStatus;
  documentCount: number;
}

export interface UploadedFile {
  name: string;
  size: string;
  date: string;
}

/** Streitpartei-Kategorien (US-9.1). */
export type OpponentCategory =
  | "strom"
  | "gas"
  | "wasser"
  | "versicherung"
  | "mobilfunk_internet"
  | "amt_behoerde"
  | "vermieter_immobilien"
  | "sonstiges";

/** Extrahiertes Feld mit Confidence-Score (US-9.2). */
export interface ExtractionField {
  key: string;
  value: string | number | null;
  confidence: number;
  needs_review: boolean;
  auto_accepted: boolean;
  source_document_id: string | null;
  source_text_snippet: string | null;
  field_ignored: boolean;
}

/** Erkannte Streitpartei (US-9.1). */
export interface OpponentData {
  category: OpponentCategory | null;
  name: string | null;
  confidence: number;
  needs_review: boolean;
}

/** Response von GET /cases/{caseId}/extraction-result (US-9.2). */
export interface ExtractionResult {
  fields: ExtractionField[];
  opponent: OpponentData;
}

/** Extrahierte und vom Nutzer bestätigbare Fall-Kerndaten (US-3.2 / US-3.5). */
export interface ExtractedData {
  malo_id: string | null;
  meter_number: string | null;
  dispute_amount: number | null;
  network_operator: string | null;
  opponent_category: string | null;
  opponent_name: string | null;
}

export interface TimelineEvent {
  event_id: string;
  case_id: string;
  event_date: string;          // "YYYY-MM-DD"
  description: string;
  source_doc_id: string | null;
  source_type: "ai" | "user";
  is_gap: boolean;
}

export interface TimelineResponse {
  status: "building" | "ready" | "empty";
  events: TimelineEvent[];
}

// ── Component prop interfaces ─────────────────────────────────────────────────

export interface WithSetPage {
  setPage: (page: Page) => void;
}

export interface WithSetLoggedIn {
  setLoggedIn: (v: boolean) => void;
}

// ── Mappers ───────────────────────────────────────────────────────────────────

const STATUS_MAP: Record<CaseStatusApi, CaseStatus> = {
  DRAFT:              "Entwurf",
  WAITING_FOR_USER:   "Wartet auf Zahlung",
  BUILDING_TIMELINE:  "Entwurf",
  TIMELINE_READY:     "Entwurf",
  PAYMENT_PENDING:    "Zahlung ausstehend",
  PAID:               "Abgeschlossen",
  GENERATING_DOSSIER: "Abgeschlossen",
  ERROR_GENERATION:   "Abgeschlossen",
  COMPLETED:          "Abgeschlossen",
};

/** Wandelt das API-Case-Format in das UI-Case-Format um. */
export function mapApiCase(c: ApiCase): Case {
  return {
    apiId: c.case_id,
    id: c.case_id.slice(-6).toUpperCase(),
    date: new Date(c.created_at).toLocaleDateString("de-DE"),
    operator: c.network_operator ?? "Netzbetreiber unbekannt",
    status: STATUS_MAP[c.status] ?? "Entwurf",
    documentCount: c.document_count,
  };
}
