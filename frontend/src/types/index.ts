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
  | "hilfe";

// ── Domain models ─────────────────────────────────────────────────────────────

export type CaseStatus = "Entwurf" | "Wartet auf Zahlung" | "Abgeschlossen";

export interface Case {
  id: string;
  date: string;
  operator: string;
  status: CaseStatus;
}

export interface UploadedFile {
  name: string;
  size: string;
  date: string;
}

export interface ExtractedData {
  malo: string;
  zaehlerNr: string;
  betrag: string;
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
