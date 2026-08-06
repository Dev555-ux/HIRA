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

// M15A: the business owner's own "is my AI live" view — Settings' AI
// Employee card and Analytics' Business Health card both describe this same
// field; this is the one place that describes it now. Deliberately distinct
// from Ops's onboardingState/onboardingLabel (app/(ops)/ops/page.tsx),
// which answers a different, founder-only question ("is this account fully
// complete" — WhatsApp connected AND a knowledge base published, not just
// onboarding_status) and stays its own presentation.
export function describeOnboardingStatus(
  status: Business["onboarding_status"] | undefined,
): { label: string; variant: "success" | "secondary" } {
  return status === "live"
    ? { label: "Live", variant: "success" }
    : { label: "Setting up", variant: "secondary" };
}

// Per-message chat timestamp ("2:34 PM"), distinct from formatRelativeTime's
// "10m ago" — a persistent transcript reads better with a fixed clock time
// than a relative one that changes every time you look at it.
export function formatMessageTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
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
// <input type="datetime-local"> expects. API values are explicit UTC, while
// the native control displays local browser time, so convert before rendering.
export function toDateTimeInputValue(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// A datetime-local input has no offset, so turn its browser-local value back
// into the explicit UTC timestamp the API uses for every stored appointment.
export function toUtcIsoFromDateTimeInput(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}
