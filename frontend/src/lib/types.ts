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

export interface KbEntry {
  id: string;
  title: string;
  chunk_count: number;
  embedding_status: "ready" | "pending" | "error";
  updated_at: string;
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
