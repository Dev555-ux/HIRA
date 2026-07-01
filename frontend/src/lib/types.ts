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
