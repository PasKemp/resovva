// ─────────────────────────────────────────────────────────────────────────────
// API Service — typisierter Client für das Resovva FastAPI-Backend
//
// Auth via HttpOnly-Cookie: credentials: "include" sorgt dafür, dass der
// Browser den Cookie bei Cross-Origin-Requests (localhost:5173 → :8000) mitsendet.
// ─────────────────────────────────────────────────────────────────────────────

import type { ApiCase, ExtractedData, TimelineEvent } from "../types";

export interface AnalysisResultResponse {
  status:          "analyzing" | "waiting_for_user" | "error";
  extracted_data?: ExtractedData & {
    currency?:     string | null;
    confirmed?:    boolean;
    extracted_at?: string;
    missing_data?: boolean;
  };
  error_message?: string | null;
}

// Empty string → relative URLs → requests go through the Vite dev-server proxy.
// This means the phone (accessing via local-network IP) hits the same Vite proxy
// and never needs to reach the backend directly — no CORS issues, no IP config.
// Override with VITE_API_URL only when running outside Vite (e.g. Storybook, tests).
const BASE_URL = import.meta.env.VITE_API_URL ?? "";

// ── Helpers ───────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include", // HttpOnly-Cookie mitsenden
    ...init,
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API ${response.status}: ${errorText}`);
  }
  return response.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginPayload {
  email:    string;
  password: string;
}

export interface RegisterPayload {
  email:          string;
  password:       string;
  accepted_terms: boolean;
  first_name:     string;
  last_name:      string;
  street:         string;
  postal_code:    string;
  city:           string;
}
export interface AuthResponse {
  status:   string;
  user_id:  string;
  message?: string;
}

export interface MeResponse {
  user_id:          string;
  email:            string;
  first_name:       string | null;
  last_name:        string | null;
  street:           string | null;
  postal_code:      string | null;
  city:             string | null;
  profile_complete: boolean;
}

export const authApi = {
  me: () =>
    apiFetch<MeResponse>("/api/v1/auth/me"),

  login: (payload: LoginPayload) =>
    apiFetch<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body:   JSON.stringify(payload),
    }),

  register: (payload: RegisterPayload) =>
    apiFetch<AuthResponse>("/api/v1/auth/register", {
      method: "POST",
      body:   JSON.stringify(payload),
    }),

  logout: () =>
    apiFetch<{ status: string }>("/api/v1/auth/logout", { method: "POST" }),

  forgotPassword: (email: string) =>
    apiFetch<{ message: string }>("/api/v1/auth/forgot-password", {
      method: "POST",
      body:   JSON.stringify({ email }),
    }),

  resetPassword: (token: string, password: string) =>
    apiFetch<{ status: string }>("/api/v1/auth/reset-password", {
      method: "POST",
      body:   JSON.stringify({ token, password }),
    }),
};

// ── Cases ─────────────────────────────────────────────────────────────────────

export interface CasesResponse {
  cases: ApiCase[];
}

export interface CreateCaseResponse {
  case_id: string;
  status:  string;
  message: string;
}

export const casesApi = {
  list:   () =>
    apiFetch<CasesResponse>("/api/v1/cases"),

  create: () =>
    apiFetch<CreateCaseResponse>("/api/v1/cases", { method: "POST" }),

  delete: (caseId: string) =>
    apiFetch<{ status: string }>(`/api/v1/cases/${caseId}`, { method: "DELETE" }),
};

// ── Documents ─────────────────────────────────────────────────────────────────

export interface UploadResponse {
  document_id: string;
  filename:    string;
  status:      string;
}

export const documentsApi = {
  upload: (caseId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    // credentials ohne Content-Type-Header – Browser setzt Boundary automatisch
    return fetch(`${BASE_URL}/api/v1/cases/${caseId}/documents`, {
      method:      "POST",
      body:        form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) throw new Error(`Upload fehlgeschlagen: ${await r.text()}`);
      return r.json() as Promise<UploadResponse>;
    });
  },

  delete: (caseId: string, fileId: string) =>
    apiFetch<void>(`/api/v1/cases/${caseId}/documents/${fileId}`, { method: "DELETE" }),
};

// ── Mobile Upload ─────────────────────────────────────────────────────────────

export interface UploadTokenResponse {
  token:      string;
  expires_at: string;
  upload_url: string;
}

export interface CaseStatusResponse {
  status:    "processing" | "completed" | "error" | "empty";
  total:     number;
  completed: number;
  preview?:  string;
}

/** Einzelnes Dokument in der Dokumentenliste eines Falls. */
export interface DocumentListItem {
  document_id:   string;
  filename:      string;
  document_type: string;
  ocr_status:    string;
  created_at:    string;
}

export interface DocumentsResponse {
  documents: DocumentListItem[];
}

export interface TokenInfoResponse {
  case_id:    string;
  expires_at: string;
  valid:      boolean;
}

export const mobileUploadApi = {
  createToken: (caseId: string) =>
    apiFetch<UploadTokenResponse>("/api/v1/upload-tokens", {
      method: "POST",
      body:   JSON.stringify({ case_id: caseId }),
    }),

  getTokenInfo: (token: string) =>
    apiFetch<TokenInfoResponse>(`/api/v1/upload-tokens/${token}/info`),

  uploadFile: (token: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE_URL}/api/v1/mobile-upload?token=${encodeURIComponent(token)}`, {
      method: "POST",
      body:   form,
      // Kein credentials: "include" – Token-Auth, kein Cookie nötig
    }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text());
      return r.json() as Promise<UploadResponse>;
    });
  },
};

export const caseStatusApi = {
  get: (caseId: string) =>
    apiFetch<CaseStatusResponse>(`/api/v1/cases/${caseId}/status`),

  listDocuments: (caseId: string) =>
    apiFetch<DocumentsResponse>(`/api/v1/cases/${caseId}/documents`),
};

// ── Case Analyze (Epic 2 → Epic 3 Brücke) ─────────────────────────────────────

export const caseAnalyzeApi = {
  start: (caseId: string) =>
    apiFetch<{ status: string; message: string }>(`/api/v1/cases/${caseId}/analyze`, {
      method: "POST",
    }),
};

// ── Analysis (Epic 3) ─────────────────────────────────────────────────────────

export const analysisApi = {
  /** Pollt das Extraktionsergebnis (404 wenn noch laufend). */
  result: (caseId: string) =>
    apiFetch<AnalysisResultResponse>(`/api/v1/cases/${caseId}/analysis/result`),

  /** Bestätigt die vom Nutzer geprüften Daten (HiTL, US-3.5). */
  confirm: (caseId: string, data: ExtractedData) =>
    apiFetch<{ status: string; next_step: string }>(`/api/v1/cases/${caseId}/analysis/confirm`, {
      method: "PUT",
      body:   JSON.stringify(data),
    }),
};

// ── Timeline ──────────────────────────────────────────────────────────────────

export const timelineApi = {
  get: (caseId: string) =>
    apiFetch<{ timeline: TimelineEvent[] }>(`/api/v1/cases/${caseId}/timeline`),

  addEvent: (caseId: string, event: Omit<TimelineEvent, "id">) =>
    apiFetch<TimelineEvent>(`/api/v1/cases/${caseId}/timeline`, {
      method: "POST",
      body:   JSON.stringify(event),
    }),
};

// ── Dossier ───────────────────────────────────────────────────────────────────

export interface DossierStatus {
  progress:      number;
  ready:         boolean;
  download_url?: string;
}

export const dossierApi = {
  generate: (caseId: string) =>
    apiFetch<{ job_id: string }>(`/api/v1/cases/${caseId}/dossier`, { method: "POST" }),

  status: (caseId: string) =>
    apiFetch<DossierStatus>(`/api/v1/cases/${caseId}/dossier/status`),
};

// ── User Profile (US-7.4) ─────────────────────────────────────────────────────

export interface UpdateProfilePayload {
  first_name: string;
  last_name:  string;
  street:     string;
  postal_code: string;
  city:        string;
}

export const profileApi = {
  update: (payload: UpdateProfilePayload) =>
    apiFetch<{ status: string }>("/api/v1/users/me", {
      method: "PUT",
      body:   JSON.stringify(payload),
    }),

  changePassword: (old_password: string, new_password: string) =>
    apiFetch<{ status: string }>("/api/v1/users/me/password", {
      method: "PUT",
      body:   JSON.stringify({ old_password, new_password }),
    }),

  deleteAccount: () =>
    fetch("/api/v1/users/me", {
      method:      "DELETE",
      credentials: "include",
    }).then(r => {
      if (!r.ok && r.status !== 204) throw new Error(`API ${r.status}`);
    }),
};

// ── Checkout ──────────────────────────────────────────────────────────────────

export const checkoutApi = {
  create: (caseId: string) =>
    apiFetch<{ checkout_url: string }>(`/api/v1/cases/${caseId}/checkout`, { method: "POST" }),
};
