import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { Business } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Maps the real backend field (Business.whatsapp_connection_status) to display
// copy — no status is invented here, only worded for a business owner instead
// of a developer.
export function describeWhatsAppConnection(
  status: Business["whatsapp_connection_status"] | undefined,
): { label: string; variant: "success" | "warning" | "secondary" } {
  switch (status) {
    case "connected":
      return { label: "Connected", variant: "success" };
    case "pending_verification":
      return { label: "Needs attention", variant: "warning" };
    case "not_connected":
    default:
      return { label: "Not connected", variant: "secondary" };
  }
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

// Converts a backend ISO datetime (or null) into the "YYYY-MM-DD" value an
// <input type="date"> expects. Used for Lead.next_follow_up_at.
export function toDateInputValue(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return iso.slice(0, 10);
}

// Converts a backend ISO datetime into the "YYYY-MM-DDTHH:mm" value an
// <input type="datetime-local"> expects. Used for Appointment.starts_at/ends_at
// (naive timestamps, so no timezone conversion is needed — see DEC-032).
export function toDateTimeInputValue(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return iso.slice(0, 16);
}
