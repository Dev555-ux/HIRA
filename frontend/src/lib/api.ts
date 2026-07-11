import { API_BASE_URL } from "./config";
import type {
  ApiEnvelope,
  ApproveResult,
  Appointment,
  AvailabilitySlot,
  Business,
  BusinessSettings,
  CalendarSettings,
  CalendarStatus,
  Conversation,
  ConversationStatusFilter,
  CreateAppointmentPayload,
  CreateBusinessPayload,
  CreateCustomerPayload,
  CreateKbEntryPayload,
  CreateLeadPayload,
  CustomerDetail,
  Customer,
  EscalateResult,
  ImportWebsitePayload,
  ImportWebsiteResult,
  KbEntry,
  Lead,
  LeadStage,
  Message,
  OnboardingStatus,
  PaginatedEnvelope,
  PendingReply,
  PlaygroundResponse,
  RegenerateResult,
  RejectResult,
  RescheduleAppointmentPayload,
  TimelineItem,
  UpdateCalendarSettingsPayload,
  UpdateCustomerPayload,
  UpdateDraftResult,
  UpdateKbEntryPayload,
  UpdateLeadPayload,
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
  if (!token) {
    throw new ApiError(401, "Not authenticated");
  }
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  headers.set("Authorization", `Bearer ${token}`);

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

  listLeads: (
    getToken: GetToken,
    params: { search?: string; stage?: LeadStage; limit?: number; offset?: number } = {},
  ) => apiFetch<PaginatedEnvelope<Lead[]>>(`/api/v1/leads${buildQuery(params)}`, getToken),

  createLead: (getToken: GetToken, payload: CreateLeadPayload) =>
    apiFetch<ApiEnvelope<Lead>>("/api/v1/leads", getToken, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  getLead: (getToken: GetToken, id: string) =>
    apiFetch<ApiEnvelope<Lead>>(`/api/v1/leads/${id}`, getToken).then((r) => r.data),

  updateLead: (getToken: GetToken, id: string, payload: UpdateLeadPayload) =>
    apiFetch<ApiEnvelope<Lead>>(`/api/v1/leads/${id}`, getToken, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  deleteLead: (getToken: GetToken, id: string) =>
    apiFetch<void>(`/api/v1/leads/${id}`, getToken, { method: "DELETE" }),

  listCustomers: (
    getToken: GetToken,
    params: { search?: string; limit?: number; offset?: number } = {},
  ) => apiFetch<PaginatedEnvelope<Customer[]>>(`/api/v1/customers${buildQuery(params)}`, getToken),

  getCustomer: (getToken: GetToken, id: string) =>
    apiFetch<ApiEnvelope<CustomerDetail>>(`/api/v1/customers/${id}`, getToken).then(
      (r) => r.data,
    ),

  createCustomer: (getToken: GetToken, payload: CreateCustomerPayload) =>
    apiFetch<ApiEnvelope<CustomerDetail>>("/api/v1/customers", getToken, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  updateCustomer: (getToken: GetToken, id: string, payload: UpdateCustomerPayload) =>
    apiFetch<ApiEnvelope<CustomerDetail>>(`/api/v1/customers/${id}`, getToken, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  deleteCustomer: (getToken: GetToken, id: string) =>
    apiFetch<void>(`/api/v1/customers/${id}`, getToken, { method: "DELETE" }),

  getCustomerTimeline: (
    getToken: GetToken,
    id: string,
    params: { limit?: number; offset?: number } = {},
  ) =>
    apiFetch<PaginatedEnvelope<TimelineItem[]>>(
      `/api/v1/customers/${id}/timeline${buildQuery(params)}`,
      getToken,
    ),

  getCalendarSettings: (getToken: GetToken) =>
    apiFetch<ApiEnvelope<CalendarSettings>>("/api/v1/calendar/settings", getToken).then(
      (r) => r.data,
    ),

  updateCalendarSettings: (getToken: GetToken, payload: UpdateCalendarSettingsPayload) =>
    apiFetch<ApiEnvelope<CalendarSettings>>("/api/v1/calendar/settings", getToken, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  startCalendarConnect: (getToken: GetToken) =>
    apiFetch<ApiEnvelope<{ authorization_url: string }>>(
      "/api/v1/calendar/oauth/connect",
      getToken,
    ).then((r) => r.data),

  getCalendarStatus: (getToken: GetToken) =>
    apiFetch<ApiEnvelope<CalendarStatus>>("/api/v1/calendar/status", getToken).then(
      (r) => r.data,
    ),

  disconnectCalendar: (getToken: GetToken) =>
    apiFetch<void>("/api/v1/calendar/disconnect", getToken, { method: "DELETE" }),

  getAvailability: (getToken: GetToken, params: { starts_at: string; ends_at: string }) =>
    apiFetch<ApiEnvelope<AvailabilitySlot[]>>(
      `/api/v1/calendar/availability${buildQuery(params)}`,
      getToken,
    ).then((r) => r.data),

  listAppointments: (
    getToken: GetToken,
    params: { from?: string; to?: string } = {},
  ) => apiFetch<ApiEnvelope<Appointment[]>>(
    `/api/v1/appointments${buildQuery(params)}`,
    getToken,
  ).then((r) => r.data),

  createAppointment: (getToken: GetToken, payload: CreateAppointmentPayload) =>
    apiFetch<ApiEnvelope<Appointment>>("/api/v1/appointments", getToken, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  getAppointment: (getToken: GetToken, id: string) =>
    apiFetch<ApiEnvelope<Appointment>>(`/api/v1/appointments/${id}`, getToken).then(
      (r) => r.data,
    ),

  rescheduleAppointment: (getToken: GetToken, id: string, payload: RescheduleAppointmentPayload) =>
    apiFetch<ApiEnvelope<Appointment>>(`/api/v1/appointments/${id}/reschedule`, getToken, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((r) => r.data),

  cancelAppointment: (getToken: GetToken, id: string) =>
    apiFetch<ApiEnvelope<Appointment>>(`/api/v1/appointments/${id}/cancel`, getToken, {
      method: "POST",
    }).then((r) => r.data),
};
