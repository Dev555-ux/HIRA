// Shared appointment display metadata — single source of truth for the
// Appointments list (Sprint 32) and the Dashboard's upcoming-appointments
// widget (Sprint 40), so the two can't drift.
import type { ActivityState } from "@/components/ui/activity-dot";
import type { Appointment } from "@/lib/types";

// Kept in full: Dashboard's upcoming-appointments widget still consumes
// this directly (out of scope for IMPLEMENTATION-ROADMAP-001 M7 — Dashboard
// isn't touched by this milestone) and can't be moved onto StatusPill here
// without a separate, explicitly-scoped change to that screen.
export const APPOINTMENT_STATUS_BADGE: Record<
  Appointment["status"],
  { label: string; variant: "success" | "warning" | "destructive" }
> = {
  booked: { label: "Booked", variant: "success" },
  rescheduled: { label: "Rescheduled", variant: "warning" },
  cancelled: { label: "Cancelled", variant: "destructive" },
};

// M7: StatusPill's status→dot-color mapping, added alongside the Badge
// mapping above rather than replacing it (Dashboard still needs that one).
// Same three colors, 1:1 — booked/rescheduled/cancelled never had the
// ambiguity lead stages did, so this is a direct success/warning/
// destructive → success/waiting/error translation, nothing collapsed.
export const APPOINTMENT_STATUS: Record<Appointment["status"], ActivityState> = {
  booked: "success",
  rescheduled: "waiting",
  cancelled: "error",
};

export function formatAppointmentRange(startsAt: string, endsAt: string): string {
  const start = new Date(startsAt);
  const end = new Date(endsAt);
  const dateLabel = start.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
  const startTime = start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const endTime = end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${dateLabel}, ${startTime} – ${endTime}`;
}
