import { API_BASE_URL } from "./config";
import type {
  ApiEnvelope,
  ApproveResult,
  Business,
  BusinessSettings,
  CreateBusinessPayload,
  CreateKbEntryPayload,
  ImportWebsitePayload,
  ImportWebsiteResult,
  KbEntry,
  OnboardingStatus,
  PendingReply,
  PlaygroundResponse,
  UpdateKbEntryPayload,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

type GetToken = () => Promise<string | null>;

async function apiFetch<T>(
  path: string,
  getToken: GetToken,
  init: RequestInit = {},
): Promise<T> {
  const token = await getToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch (err) {
    throw new ApiError(0, `Network error: ${(err as Error).message}`);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? body?.error?.message ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// Typed client. Each method takes the token getter so auth stays centralized.
export const api = {
  listPending: (getToken: GetToken) =>
    apiFetch<ApiEnvelope<PendingReply[]>>("/api/v1/pending", getToken).then(
      (r) => r.data,
    ),

  approveMessage: (getToken: GetToken, messageId: string) =>
    apiFetch<ApiEnvelope<ApproveResult>>(
      `/api/v1/messages/${messageId}/approve`,
      getToken,
      { method: "POST" },
    ).then((r) => r.data),

  getOnboardingStatus: (getToken: GetToken) =>
    apiFetch<ApiEnvelope<OnboardingStatus>>("/api/v1/onboarding/status", getToken).then(
      (r) => r.data,
    ),

  createBusiness: (getToken: GetToken, payload: CreateBusinessPayload) =>
    apiFetch<ApiEnvelope<Business>>("/api/v1/onboarding/business", getToken, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  listKbEntries: (getToken: GetToken) =>
    apiFetch<ApiEnvelope<KbEntry[]>>("/api/v1/kb", getToken).then((r) => r.data),

  createKbEntry: (getToken: GetToken, payload: CreateKbEntryPayload) =>
    apiFetch<ApiEnvelope<KbEntry[]>>("/api/v1/kb", getToken, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  updateKbEntry: (getToken: GetToken, id: string, payload: UpdateKbEntryPayload) =>
    apiFetch<ApiEnvelope<KbEntry>>(`/api/v1/kb/${id}`, getToken, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  deleteKbEntry: (getToken: GetToken, id: string) =>
    apiFetch<void>(`/api/v1/kb/${id}`, getToken, { method: "DELETE" }),

  importWebsite: (getToken: GetToken, payload: ImportWebsitePayload) =>
    apiFetch<ImportWebsiteResult>("/api/v1/kb/website", getToken, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  sendPlaygroundMessage: (getToken: GetToken, message: string) =>
    apiFetch<ApiEnvelope<PlaygroundResponse>>(
      "/api/v1/onboarding/playground/message",
      getToken,
      { method: "POST", body: JSON.stringify({ message }) },
    ).then((r) => r.data),

  getSettings: (getToken: GetToken) =>
    apiFetch<ApiEnvelope<BusinessSettings>>("/api/v1/settings", getToken).then(
      (r) => r.data,
    ),

  updateSettings: (getToken: GetToken, payload: BusinessSettings) =>
    apiFetch<ApiEnvelope<BusinessSettings>>("/api/v1/settings", getToken, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }).then((r) => r.data),
};
