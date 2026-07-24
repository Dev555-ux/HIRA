// Types mirroring the backend API contracts (documentation/API.md).

export interface PendingReplyCustomer {
  id: string;
  display_name: string | null;
  wa_phone: string;
}

export interface PendingReply {
  id: string;
  conversation_id: string;
  body: string;
  created_at: string;
  customer: PendingReplyCustomer | null;
  conversation_preview: string | null;
}

export interface ApproveResult {
  id: string;
  status: "sent" | "failed" | "pending_approval";
}

export interface UpdateDraftResult {
  id: string;
  body: string;
  status: "pending_approval";
}

export interface RejectResult {
  id: string;
  status: "rejected";
}

export interface RegenerateResult {
  id: string;
  body: string;
  status: "pending_approval";
}

export interface EscalationInfo {
  id: string;
  conversation_id: string;
  reason: string;
  status: string;
  created_at: string;
}

export interface EscalateResult {
  id: string;
  status: "escalated";
  escalation: EscalationInfo;
}

export interface ApiEnvelope<T> {
  data: T;
}

export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface PaginatedEnvelope<T> {
  data: T;
  meta: PaginationMeta;
}

// Conversations / Inbox (/api/v1/conversations). Status filter chips map to
// Conversation.status plus a derived "pending" view (see backend/app/api/
// conversations.py's module docstring for the exact filter semantics).
export type ConversationStatusFilter = "open" | "pending" | "closed";

export interface ConversationCustomer {
  id: string;
  display_name: string | null;
  wa_phone: string;
}

export interface Conversation {
  id: string;
  status: "active" | "escalated" | "closed";
  customer: ConversationCustomer;
  last_message_at: string | null;
  preview: string | null;
  has_pending_approval: boolean;
  created_at: string;
}

export interface Message {
  id: string;
  direction: "inbound" | "outbound";
  body: string;
  type: string;
  status: "received" | "pending_approval" | "sent" | "failed" | "rejected" | "escalated";
  created_at: string;
}

// Leads / CRM pipeline (/api/v1/leads). Sprint 28 — see DEC-031. `stage` is
// validated against this fixed set at the API boundary, but stored as a plain
// string on the backend (no DB-level enum), matching Message.status/
// Conversation.status.
export type LeadStage =
  | "new"
  | "contacted"
  | "qualified"
  | "proposal_sent"
  | "negotiation"
  | "won"
  | "lost";

export interface LeadCustomer {
  id: string;
  display_name: string | null;
  company: string | null;
  wa_phone: string | null;
  email: string | null;
}

// Fields shared between the standalone /leads response and the lead embedded
// in a /customers/{id} response (which omits `customer` — redundant there).
export interface LeadFields {
  id: string;
  stage: LeadStage;
  source: string | null;
  estimated_value: number | null;
  notes: string | null;
  next_follow_up_at: string | null;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface Lead extends LeadFields {
  customer: LeadCustomer;
}

export type CustomerLead = LeadFields;

// Sprint 38 — manual lead creation. Either `customer_id` (an already-known
// customer), or enough contact info for the backend to find/create one
// (resolve_or_create_customer: customer_id -> phone match -> email match ->
// create new from display_name/company/wa_phone/email). display_name is
// only actually required when a new customer needs to be created — the
// backend enforces that conditionally, not this type.
export interface CreateLeadPayload {
  customer_id?: string;
  display_name?: string;
  company?: string | null;
  wa_phone?: string | null;
  email?: string | null;
  stage?: LeadStage;
  source?: string | null;
  estimated_value?: number | null;
  notes?: string | null;
  next_follow_up_at?: string | null;
  assigned_to?: string | null;
}

// All fields optional-and-nullable: omitting a key leaves it untouched,
// sending `null` explicitly clears it (see backend's `exclude_unset` handling).
export interface UpdateLeadPayload {
  stage?: LeadStage;
  source?: string | null;
  estimated_value?: number | null;
  notes?: string | null;
  next_follow_up_at?: string | null;
  assigned_to?: string | null;
}

// Customers (/api/v1/customers). Sprint 28 — see DEC-031.
export interface LeadSummary {
  id: string;
  stage: LeadStage;
}

export interface Customer {
  id: string;
  display_name: string | null;
  company: string | null;
  wa_phone: string | null;
  email: string | null;
  notes: string | null;
  created_at: string;
  conversation_count: number;
  last_message_at: string | null;
  lead: LeadSummary | null;
}

export interface CustomerDetail extends Omit<Customer, "lead"> {
  lead: CustomerLead | null;
}

// Manual customer management (Sprint 37). Creating/updating a customer here
// never creates a Lead, Conversation, or Message, and never sends WhatsApp.
export interface CreateCustomerPayload {
  display_name: string;
  company?: string | null;
  wa_phone?: string | null;
  email?: string | null;
  notes?: string | null;
}

// All fields optional: omitting a key leaves it untouched (see backend's
// exclude_unset handling), same convention as UpdateLeadPayload.
export interface UpdateCustomerPayload {
  display_name?: string;
  company?: string | null;
  wa_phone?: string | null;
  email?: string | null;
  notes?: string | null;
}

// Customer timeline (/api/v1/customers/{id}/timeline) — merges Message
// history with Lead activity (LeadEvent rows), newest first.
export interface TimelineMessageItem {
  type: "message";
  id: string;
  created_at: string;
  direction: Message["direction"];
  body: string;
  status: Message["status"];
}

export type LeadEventType =
  | "lead_created"
  | "stage_change"
  | "notes_updated"
  | "follow_up_set"
  | "assigned";

export interface TimelineLeadEventItem {
  type: "lead_event";
  id: string;
  created_at: string;
  event_type: LeadEventType;
  from_value: string | null;
  to_value: string | null;
  note: string | null;
}

export type TimelineItem = TimelineMessageItem | TimelineLeadEventItem;

// Calendar (/api/v1/calendar). Sprint 29 — see DEC-032. working_hours is a
// day -> {open, close} map ("HH:MM" 24-hour), a day's value null for closed;
// the whole field is null when the business hasn't configured hours yet.
export interface WorkingHoursDay {
  open: string;
  close: string;
}

export type WorkingHours = Partial<Record<
  "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun",
  WorkingHoursDay | null
>>;

export interface CalendarSettings {
  timezone: string;
  working_hours: WorkingHours | null;
}

export interface UpdateCalendarSettingsPayload {
  timezone?: string;
  working_hours?: WorkingHours | null;
}

export interface CalendarStatus {
  connected: boolean;
  calendar_id: string | null;
}

// WhatsApp self-serve connection (Sprint 69, /api/v1/whatsapp).
export interface WhatsAppStatus {
  connected: boolean;
  status: "not_connected" | "pending_verification" | "connected";
  phone_number_id_masked: string | null;
  connected_at: string | null;
}

export interface ConnectWhatsAppPayload {
  phone_number_id: string;
  whatsapp_business_account_id: string;
  access_token: string;
  app_secret: string;
}

export interface AvailabilitySlot {
  starts_at: string;
  ends_at: string;
}

// Appointments (/api/v1/appointments).
export interface AppointmentCustomer {
  id: string;
  display_name: string | null;
  wa_phone: string;
}

export interface Appointment {
  id: string;
  customer: AppointmentCustomer | null;
  conversation_id: string | null;
  starts_at: string;
  ends_at: string;
  status: "booked" | "rescheduled" | "cancelled";
  created_at: string;
  updated_at: string;
}

export interface CreateAppointmentPayload {
  customer_id: string;
  starts_at: string;
  ends_at: string;
  summary: string;
  conversation_id?: string;
}

export interface RescheduleAppointmentPayload {
  starts_at: string;
  ends_at: string;
}

// Knowledge Base — manual entry (/api/v1/kb). Each entry may be one of
// several chunks stored under the same title if the content was long enough
// to split (see backend/app/ai/chunking.py); manual FAQ-length entries are
// almost always a single chunk.
//
// Draft -> Review -> Approve -> Publish (DEC-039): manual entries are always
// "published" immediately. Website imports come back "draft" and only ever
// appear here (GET /kb) once approved — see KbDraftBatch/GET /kb/drafts.
export interface KbEntry {
  id: string;
  title: string;
  content: string;
  status: "draft" | "published";
  import_batch_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateKbEntryPayload {
  title: string;
  content: string;
}

export interface UpdateKbEntryPayload {
  title?: string;
  content?: string;
}

// Website import (/api/v1/kb/website) — fetches one page, cleans it, and
// indexes it the same way a manual entry is, but as a draft pending review
// (not immediately live). Unlike the other /kb endpoints, the backend
// returns this shape directly (not wrapped in {data: ...}).
export interface ImportWebsitePayload {
  url: string;
}

export interface ImportWebsiteResult {
  pages_imported: number;
  entries_created: number;
  import_batch_id: string;
  // What was actually imported, not just the count — shown in the post-import
  // summary. Every chunk from one page shares the page's title (see the
  // KbEntry comment above), so it's the content, not the title, that varies.
  entries: { id: string; title: string; content: string }[];
}

// One website import's worth of draft entries awaiting review together —
// see GET /api/v1/kb/drafts.
export interface KbDraftBatch {
  import_batch_id: string;
  entries: KbEntry[];
}

// Demo Chat (/api/v1/onboarding/playground/*, formerly "Playground") — a
// second transport onto the exact same generate_reply() pipeline the
// WhatsApp webhook uses; see backend/app/ai/playground.py.
export interface PlaygroundKbEntry {
  id: string;
  title: string;
  content: string;
}

// Present only when the reply involved a proposed tool call (a booking, a
// lead) — Demo Chat executes it immediately (no human reviewer on a demo
// conversation), so this reports what actually happened.
export interface PlaygroundToolOutcome {
  name: string;
  success: boolean;
}

export interface PlaygroundResponse {
  reply: string;
  model: string;
  retrieved: PlaygroundKbEntry[];
  tool: PlaygroundToolOutcome | null;
}

export interface PlaygroundHistory {
  conversation_id: string;
  messages: Message[];
}

export interface AnalyticsSummary {
  total_conversations: number;
  messages_today: number;
  pending_approvals: number;
  avg_response_seconds: number | null;
}

// Onboarding (Milestone A — business provisioning only).
export interface Business {
  id: string;
  name: string;
  industry: string | null;
  contact_email: string | null;
  country: string | null;
  timezone: string;
  onboarding_status: "created" | "live";
  whatsapp_connection_status: "not_connected" | "pending_verification" | "connected";
}

export interface OnboardingStatus {
  has_business: boolean;
  business: Business | null;
}

export interface CreateBusinessPayload {
  name: string;
  owner_email: string;
  industry?: string;
  contact_email?: string;
  country?: string;
  timezone?: string;
}

// AI Reply Mode (/api/v1/settings). "assisted" leaves every AI reply pending
// a human's approval; "autonomous" sends it to the customer immediately.
export type AiReplyMode = "assisted" | "autonomous";

export interface BusinessSettings {
  mode: AiReplyMode;
}
