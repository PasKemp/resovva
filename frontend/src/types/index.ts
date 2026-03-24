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
export type CaseStatusApi = "DRAFT" | "WAITING_FOR_USER" | "PAID" | "COMPLETED";

/** Deutsche Anzeigebezeichnungen für das UI */
export type CaseStatus = "Entwurf" | "Wartet auf Zahlung" | "Abgeschlossen";

/** API-Response-Format von GET /cases */
export interface ApiCase {
  case_id: string;
  created_at: string;
  status: CaseStatusApi;
  network_operator: string | null;
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

/** Extrahierte und vom Nutzer bestätigbare Fall-Kerndaten (US-3.2 / US-3.5). */
export interface ExtractedData {
  malo_id:          string | null;
  meter_number:     string | null;
  dispute_amount:   number | null;
  network_operator: string | null;
}

export interface TimelineEvent {
  date: string;
  event: string;
  source: "E-Mail" | "Foto" | "Post" | "Telefonat" | "Sonstiges";
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
  DRAFT:            "Entwurf",
  WAITING_FOR_USER: "Wartet auf Zahlung",
  PAID:             "Wartet auf Zahlung",
  COMPLETED:        "Abgeschlossen",
};

/** Wandelt das API-Case-Format in das UI-Case-Format um. */
export function mapApiCase(c: ApiCase): Case {
  return {
    apiId:         c.case_id,
    id:            c.case_id.slice(-6).toUpperCase(),
    date:          new Date(c.created_at).toLocaleDateString("de-DE"),
    operator:      c.network_operator ?? "Netzbetreiber unbekannt",
    status:        STATUS_MAP[c.status] ?? "Entwurf",
    documentCount: c.document_count,
  };
}
