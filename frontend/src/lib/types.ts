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
  review?: ReviewMetadata | null;
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

// AI Activity feed (/api/v1/activity, Sprint 84 — Dashboard Foundation).
// Read-only narrative view over execution_traces; see backend/app/services/
// execution_traces.py::list_activity_for_dashboard for how `summary` and
// `outcome` are derived (never fabricated — every field traces to a real
// trace/message).
export type AiActivityOutcome =
  | "sent"
  | "pending_approval"
  | "sending"
  | "rejected"
  | "escalated"
  | "failed";

export interface AiActivityCustomer {
  id: string;
  display_name: string | null;
}

export interface AiActivityEntry {
  id: string;
  conversation_id: string;
  customer: AiActivityCustomer | null;
  category: "conversation" | "capability" | "knowledge" | "action";
  outcome: AiActivityOutcome;
  summary: string;
  created_at: string;
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
export type ConversationStatusFilter = "open" | "pending" | "closed" | "escalated";

// Escalation Queue Workspace (/api/v1/escalations, Sprint 69, DEC-040).
// Created by POST /messages/{id}/escalate; this is the read/manage side.
export type EscalationReason =
  | "low_confidence"
  | "customer_request"
  | "external_failure"
  | "automation_failed"
  | "other";
export type EscalationStatusFilter = "open" | "resolved";
export type EscalationAssignedFilter = "mine" | "unassigned";

export interface EscalationUserRef {
  id: string;
  email: string | null;
}

export interface Escalation {
  id: string;
  reason: EscalationReason;
  status: "open" | "resolved";
  assigned_to: EscalationUserRef | null;
  resolved_by: EscalationUserRef | null;
  resolved_at: string | null;
  created_at: string;
  conversation: {
    id: string;
    customer: {
      id: string;
      display_name: string | null;
      wa_phone: string | null;
    };
  };
}

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

// AI review metadata (backend: app/api/review_metadata.py). Additive and
// optional — payloads from before this field shipped simply omit it, so every
// consumer treats `review` as possibly-undefined.
export interface GroundingSource {
  title: string | null;
  type: string | null;
  snippet: string | null;
}

export interface ReviewMetadata {
  reply_id: string;
  // null until the pipeline records a real score — never fabricated.
  confidence: { score: number | null; level: "high" | "medium" | "low" | null } | null;
  grounding: { retrieved_count: number; sources: GroundingSource[] } | null;
  generation_status: "complete" | "failed" | "working" | "idle";
}

export interface Message {
  id: string;
  direction: "inbound" | "outbound";
  body: string;
  type: string;
  status: "received" | "pending_approval" | "sending" | "sent" | "failed" | "rejected" | "escalated";
  created_at: string;
  review?: ReviewMetadata | null;
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
  // Sprint 72: the real, dialable number (e.g. "+1 555 123 4567") — unlike
  // phone_number_id_masked, never masked, since the owner needs to read it
  // in full to know which number to text during verification.
  display_phone_number: string | null;
  connected_at: string | null;
  // Sprint 71: the most recent real inbound Message's timestamp, or null if
  // none has ever arrived — the only honest signal that the webhook is
  // actually receiving traffic (credentials verifying is not proof of that).
  last_inbound_at: string | null;
}

export interface ConnectWhatsAppPayload {
  phone_number_id: string;
  whatsapp_business_account_id: string;
  access_token: string;
  app_secret: string;
}

// Sprint 71, Task A: static values every business pastes into their own
// Meta App's webhook configuration. Same for every business — the verify
// token is intentionally shared, not a secret (DEC-038).
export interface WhatsAppWebhookConfig {
  callback_url: string;
  verify_token: string;
}

// WhatsApp Embedded Signup (Track B prep, TODOS.md ONBOARD-E). Placeholder
// surface — /api/v1/whatsapp/embedded-signup/* 404s unless
// ENABLE_EMBEDDED_SIGNUP is set on the backend.
export interface EmbeddedSignupConfig {
  enabled: boolean;
}

export interface EmbeddedSignupSession {
  config_id: string;
  state: string;
}

export interface EmbeddedSignupResult {
  success: boolean;
  display_phone_number: string | null;
  error: string | null;
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

// Founder Operations Dashboard (Sprint 73, GET /api/v1/founder/overview).
// Internal-only — not shown anywhere a business owner can reach.
export type FounderAlert =
  | "whatsapp_disconnected"
  | "missing_knowledge_base"
  | "ai_failures"
  | "no_recent_activity";

export interface FounderSummary {
  total_businesses: number;
  connected_businesses: number;
  active_businesses: number;
  messages_today: number;
  ai_responses_today: number;
  failed_responses_today: number;
  avg_response_time_seconds: number | null;
}

export interface FounderBusinessRow {
  id: string;
  name: string;
  created_at: string;
  onboarding_status: "created" | "live";
  onboarding_complete: boolean;
  whatsapp: {
    status: "not_connected" | "pending_verification" | "connected";
    display_phone_number: string | null;
    credential_stored: boolean;
    last_inbound_at: string | null;
    last_outbound_at: string | null;
  };
  knowledge_base: {
    published_count: number;
    draft_count: number;
    last_updated_at: string | null;
  };
  ai_activity: {
    conversations: number;
    ai_responses: number;
    failed_responses: number;
    avg_response_time_seconds: number | null;
  };
  last_activity_at: string | null;
  alerts: FounderAlert[];
}

export interface FounderOverview {
  summary: FounderSummary;
  businesses: FounderBusinessRow[];
}

// AI Employee Observability (Sprint 76, GET /api/v1/founder/ai-metrics,
// /api/v1/founder/traces). Also internal-only.
export interface FounderAiMetrics {
  total_turns: number;
  employee_utilisation: Record<string, number>;
  most_used_employee: string | null;
  most_used_tools: { tool_name: string; count: number }[];
  failed_tool_executions: number;
  governance_blocks: number;
  avg_plan_length: number;
  avg_execution_time_ms: number;
}

export type TraceOutcome =
  | "sent"
  | "pending_approval"
  | "sending"
  | "failed"
  | "rejected"
  | "escalated"
  | "no_result";

export interface FounderTraceRow {
  id: string;
  business_id: string;
  business_name: string | null;
  category: string;
  plan_step_count: number;
  roles: string[];
  outcome: TraceOutcome;
  duration_ms: number;
  created_at: string;
}

export interface FounderPlanStep {
  domain: string;
  action: string | null;
  role: string | null;
  tools: string[];
}

export interface FounderExecutionPlan {
  category: string;
  steps: FounderPlanStep[];
  clarification_hint: string | null;
}

export interface FounderProposedToolCall {
  tool_name: string;
  agent_role: string | null;
}

export interface FounderTraceResultMessage {
  id: string;
  type: string;
  body: string;
  status: string;
  ai_meta: Record<string, unknown> | null;
}

export interface FounderTraceDetail {
  id: string;
  business_id: string;
  business_name: string | null;
  conversation_id: string;
  category: string;
  customer_message: string | null;
  plan: FounderExecutionPlan;
  proposed_tool_calls: FounderProposedToolCall[];
  result_messages: FounderTraceResultMessage[];
  outcome: TraceOutcome;
  duration_ms: number;
  created_at: string;
}

// Analytics (Analytics Phase 1, GET /api/v1/analytics/dashboard). One
// business-scoped request powers the whole page — see app/services/
// analytics.py, the same aggregation module Founder Ops draws from
// (business_id-scoped here vs. cross-tenant there). Unlike most endpoints
// in this app, the response is NOT wrapped in {"data": ...} — the handler
// returns this shape directly (confirmed by its own tests asserting these
// as the top-level response keys).
export type AnalyticsRange = "7d" | "30d" | "90d";

export interface AnalyticsOverview {
  total_conversations: number;
  messages_today: number;
  ai_responses_today: number;
  failed_responses_today: number;
  avg_response_time_seconds: number | null;
}

export interface AnalyticsBusinessHealth {
  onboarding_status: Business["onboarding_status"];
  trial_ends_at: string | null;
  created_at: string;
  whatsapp: {
    status: Business["whatsapp_connection_status"];
    display_phone_number: string | null;
  };
  knowledge_base: {
    published_count: number;
    draft_count: number;
    last_updated_at: string | null;
  };
  alerts: FounderAlert[];
  conversations_by_status: Record<string, number>;
  leads_by_stage: Record<string, number>;
  leads_by_source: Record<string, number>;
  appointments_by_status: Record<string, number>;
}

export interface AnalyticsTrendPoint {
  date: string;
  count: number;
}

export interface AnalyticsTrends {
  conversations: AnalyticsTrendPoint[];
  messages: AnalyticsTrendPoint[];
  leads: AnalyticsTrendPoint[];
  appointments: AnalyticsTrendPoint[];
}

export interface AnalyticsAiImpact {
  conversations_handled: number;
  human_escalations: number;
  leads_created: number;
  appointments_booked: number;
  kb_grounded_replies: number;
  ai_responses: number;
  estimated_hours_saved: number;
}

export interface AnalyticsDashboard {
  range: AnalyticsRange;
  overview: AnalyticsOverview;
  business_health: AnalyticsBusinessHealth;
  trends: AnalyticsTrends;
  ai_impact: AnalyticsAiImpact;
  // Byte-for-byte the same shape as FounderAiMetrics (both come from
  // app/services/analytics.py's ai_metrics()) — reused directly rather than
  // duplicated, so AiMetricsSummary (components/ai-metrics-section.tsx) can
  // render either without a translation layer.
  ai_performance: FounderAiMetrics;
}
