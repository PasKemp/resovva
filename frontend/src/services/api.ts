// ─────────────────────────────────────────────────────────────────────────────
// API Service — typed client stubs for the Resovva FastAPI backend
//
// Replace BASE_URL and implement real fetch calls as the backend endpoints
// become available. All functions are async and return typed responses.
// ─────────────────────────────────────────────────────────────────────────────

import type { Case, ExtractedData, TimelineEvent } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ── Helpers ───────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginPayload  { email: string; password: string; }
export interface AuthResponse  { token: string; userId: string; }

export const authApi = {
  login:    (payload: LoginPayload) =>
    apiFetch<AuthResponse>("/api/v1/auth/login",    { method: "POST", body: JSON.stringify(payload) }),
  register: (payload: LoginPayload & { name: string }) =>
    apiFetch<AuthResponse>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(payload) }),
};

// ── Cases ─────────────────────────────────────────────────────────────────────

export const casesApi = {
  list:   ()         => apiFetch<Case[]>("/api/v1/cases"),
  create: ()         => apiFetch<Case>("/api/v1/cases", { method: "POST" }),
  get:    (id: string) => apiFetch<Case>(`/api/v1/cases/${id}`),
  delete: (id: string) => apiFetch<void>(`/api/v1/cases/${id}`, { method: "DELETE" }),
};

// ── Documents ─────────────────────────────────────────────────────────────────

export interface UploadResponse { fileId: string; name: string; size: number; }

export const documentsApi = {
  upload: (caseId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<UploadResponse>(`/api/v1/cases/${caseId}/documents`, {
      method:  "POST",
      body:    form,
      headers: {},           // Let browser set Content-Type with boundary
    });
  },
  delete: (caseId: string, fileId: string) =>
    apiFetch<void>(`/api/v1/cases/${caseId}/documents/${fileId}`, { method: "DELETE" }),
};

// ── Analysis ──────────────────────────────────────────────────────────────────

export const analysisApi = {
  start:  (caseId: string) =>
    apiFetch<{ jobId: string }>(`/api/v1/cases/${caseId}/analysis`, { method: "POST" }),
  result: (caseId: string) =>
    apiFetch<ExtractedData>(`/api/v1/cases/${caseId}/analysis/result`),
  confirm: (caseId: string, data: ExtractedData) =>
    apiFetch<void>(`/api/v1/cases/${caseId}/analysis/confirm`, {
      method: "PUT",
      body:   JSON.stringify(data),
    }),
};

// ── Timeline ──────────────────────────────────────────────────────────────────

export const timelineApi = {
  get:    (caseId: string) =>
    apiFetch<TimelineEvent[]>(`/api/v1/cases/${caseId}/timeline`),
  addEvent: (caseId: string, event: Omit<TimelineEvent, "id">) =>
    apiFetch<TimelineEvent>(`/api/v1/cases/${caseId}/timeline`, {
      method: "POST",
      body:   JSON.stringify(event),
    }),
};

// ── Dossier ───────────────────────────────────────────────────────────────────

export interface DossierStatus { progress: number; ready: boolean; downloadUrl?: string; }

export const dossierApi = {
  generate: (caseId: string) =>
    apiFetch<{ jobId: string }>(`/api/v1/cases/${caseId}/dossier`, { method: "POST" }),
  status: (caseId: string) =>
    apiFetch<DossierStatus>(`/api/v1/cases/${caseId}/dossier/status`),
};

// ── Checkout ──────────────────────────────────────────────────────────────────

export interface CheckoutSession { sessionId: string; url: string; }

export const checkoutApi = {
  create: (caseId: string) =>
    apiFetch<CheckoutSession>(`/api/v1/cases/${caseId}/checkout`, { method: "POST" }),
};
