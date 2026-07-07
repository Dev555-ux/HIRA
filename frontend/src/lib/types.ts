// Types mirroring the backend API contracts (documentation/API.md).

export interface PendingReply {
  id: string;
  conversation_id: string;
  body: string;
  created_at: string;
}

export interface ApproveResult {
  id: string;
  status: "sent" | "failed" | "pending_approval";
}

export interface ApiEnvelope<T> {
  data: T;
}

// Types for endpoints not yet implemented on the backend (rendered from
// placeholder/empty states until those endpoints land).
export interface Conversation {
  id: string;
  customer_name: string | null;
  customer_phone: string;
  status: "active" | "escalated" | "closed";
  last_message_at: string | null;
  preview: string;
}

export interface Message {
  id: string;
  direction: "inbound" | "outbound";
  body: string;
  status: string;
  created_at: string;
}

export interface Customer {
  id: string;
  display_name: string | null;
  wa_phone: string;
  conversation_count: number;
  last_message_at: string | null;
}

// Knowledge Base — manual entry (/api/v1/kb). Each entry may be one of
// several chunks stored under the same title if the content was long enough
// to split (see backend/app/ai/chunking.py); manual FAQ-length entries are
// almost always a single chunk.
export interface KbEntry {
  id: string;
  title: string;
  content: string;
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
// indexes it the same way a manual entry is. Unlike the other /kb endpoints,
// the backend returns this shape directly (not wrapped in {data: ...}).
export interface ImportWebsitePayload {
  url: string;
}

export interface ImportWebsiteResult {
  pages_imported: number;
  entries_created: number;
}

// AI Playground (/api/v1/onboarding/playground/message) — a synchronous
// test-drive of the same generate_reply() pipeline the WhatsApp webhook uses.
export interface PlaygroundKbEntry {
  id: string;
  title: string;
  content: string;
}

export interface PlaygroundResponse {
  reply: string;
  model: string;
  retrieved: PlaygroundKbEntry[];
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
