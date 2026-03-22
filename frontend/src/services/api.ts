// ─────────────────────────────────────────────────────────────────────────────
// API Service — typisierter Client für das Resovva FastAPI-Backend
//
// Auth via HttpOnly-Cookie: credentials: "include" sorgt dafür, dass der
// Browser den Cookie bei Cross-Origin-Requests (localhost:5173 → :8000) mitsendet.
// ─────────────────────────────────────────────────────────────────────────────

import type { ApiCase, ExtractedData, TimelineEvent } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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

export interface LoginPayload    { email: string; password: string; }
export interface RegisterPayload { email: string; password: string; accepted_terms: boolean; }
export interface AuthResponse    { status: string; user_id: string; message?: string; }

export const authApi = {
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

export interface CasesResponse   { cases: ApiCase[]; }
export interface CreateCaseResponse { case_id: string; status: string; message: string; }

export const casesApi = {
  list:   () =>
    apiFetch<CasesResponse>("/api/v1/cases"),

  create: () =>
    apiFetch<CreateCaseResponse>("/api/v1/cases", { method: "POST" }),

  delete: (caseId: string) =>
    apiFetch<{ status: string }>(`/api/v1/cases/${caseId}`, { method: "DELETE" }),
};

// ── Documents ─────────────────────────────────────────────────────────────────

export interface UploadResponse { document_id: string; filename: string; status: string; }

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

// ── Analysis ──────────────────────────────────────────────────────────────────

export const analysisApi = {
  start:   (caseId: string) =>
    apiFetch<{ job_id: string }>(`/api/v1/cases/${caseId}/analysis`, { method: "POST" }),

  result:  (caseId: string) =>
    apiFetch<ExtractedData>(`/api/v1/cases/${caseId}/analysis/result`),

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

export interface DossierStatus { progress: number; ready: boolean; download_url?: string; }

export const dossierApi = {
  generate: (caseId: string) =>
    apiFetch<{ job_id: string }>(`/api/v1/cases/${caseId}/dossier`, { method: "POST" }),

  status: (caseId: string) =>
    apiFetch<DossierStatus>(`/api/v1/cases/${caseId}/dossier/status`),
};

// ── Checkout ──────────────────────────────────────────────────────────────────

export const checkoutApi = {
  create: (caseId: string) =>
    apiFetch<{ checkout_url: string }>(`/api/v1/cases/${caseId}/checkout`, { method: "POST" }),
};
