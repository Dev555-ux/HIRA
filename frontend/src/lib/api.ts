import { API_BASE_URL } from "./config";
import type {
  ApiEnvelope,
  ApproveResult,
  Business,
  BusinessSettings,
  Conversation,
  ConversationStatusFilter,
  CreateBusinessPayload,
  CreateKbEntryPayload,
  EscalateResult,
  ImportWebsitePayload,
  ImportWebsiteResult,
  KbEntry,
  Message,
  OnboardingStatus,
  PaginatedEnvelope,
  PendingReply,
  PlaygroundResponse,
  RegenerateResult,
  RejectResult,
  UpdateDraftResult,
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

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

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

  updateDraft: (getToken: GetToken, messageId: string, body: string) =>
    apiFetch<ApiEnvelope<UpdateDraftResult>>(
      `/api/v1/messages/${messageId}/draft`,
      getToken,
      { method: "PATCH", body: JSON.stringify({ body }) },
    ).then((r) => r.data),

  rejectMessage: (getToken: GetToken, messageId: string) =>
    apiFetch<ApiEnvelope<RejectResult>>(
      `/api/v1/messages/${messageId}/reject`,
      getToken,
      { method: "POST" },
    ).then((r) => r.data),

  regenerateMessage: (getToken: GetToken, messageId: string) =>
    apiFetch<ApiEnvelope<RegenerateResult>>(
      `/api/v1/messages/${messageId}/regenerate`,
      getToken,
      { method: "POST" },
    ).then((r) => r.data),

  escalateMessage: (getToken: GetToken, messageId: string) =>
    apiFetch<ApiEnvelope<EscalateResult>>(
      `/api/v1/messages/${messageId}/escalate`,
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

  listConversations: (
    getToken: GetToken,
    params: {
      search?: string;
      status?: ConversationStatusFilter;
      limit?: number;
      offset?: number;
    } = {},
  ) =>
    apiFetch<PaginatedEnvelope<Conversation[]>>(
      `/api/v1/conversations${buildQuery(params)}`,
      getToken,
    ),

  getConversation: (getToken: GetToken, id: string) =>
    apiFetch<ApiEnvelope<Conversation>>(`/api/v1/conversations/${id}`, getToken).then(
      (r) => r.data,
    ),

  listMessages: (
    getToken: GetToken,
    id: string,
    params: { limit?: number; offset?: number } = {},
  ) =>
    apiFetch<PaginatedEnvelope<Message[]>>(
      `/api/v1/conversations/${id}/messages${buildQuery(params)}`,
      getToken,
    ),
};
