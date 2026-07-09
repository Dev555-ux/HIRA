// Minimal seam for future multi-channel support (Sprint 32, DEC-035). WhatsApp
// is the only channel today and the backend sends no channel field on
// Conversation/Message — DEFAULT_CHANNEL is a client-side constant, not real
// data. The one thing this prepares is a place a second channel's icon/label
// would be added later, without restructuring how conversations are rendered.
import { MessageCircle, type LucideIcon } from "lucide-react";

export type Channel = "whatsapp";

export const DEFAULT_CHANNEL: Channel = "whatsapp";

export const CHANNELS: Record<Channel, { label: string; icon: LucideIcon }> = {
  whatsapp: { label: "WhatsApp", icon: MessageCircle },
};
