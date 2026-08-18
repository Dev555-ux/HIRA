// Minimal seam for multi-channel support (Sprint 32, DEC-035). Sprint 65 PR 4:
// the backend now sends a real `channel` field on Conversation
// (app/models.py::Conversation.channel) — DEFAULT_CHANNEL stays only as the
// fallback for the rare caller that doesn't have a conversation yet.
import { Camera, MessageCircle, type LucideIcon } from "lucide-react";

export type Channel = "whatsapp" | "instagram";

export const DEFAULT_CHANNEL: Channel = "whatsapp";

// lucide-react ships no branded Instagram mark — Camera is the same
// generic-icon convention used elsewhere for platforms without one.
export const CHANNELS: Record<Channel, { label: string; icon: LucideIcon }> = {
  whatsapp: { label: "WhatsApp", icon: MessageCircle },
  instagram: { label: "Instagram", icon: Camera },
};
