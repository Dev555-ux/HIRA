import { API_BASE_URL } from "./config";
import type {
  ApiEnvelope,
  ApproveResult,
  Business,
  CreateBusinessPayload,
  OnboardingStatus,
  PendingReply,
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
};
