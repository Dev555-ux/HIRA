// Shared appointment display metadata — single source of truth for the
// Appointments list (Sprint 32) and the Dashboard's upcoming-appointments
// widget (Sprint 40), so the two can't drift.
import type { Appointment } from "@/lib/types";

export const APPOINTMENT_STATUS_BADGE: Record<
  Appointment["status"],
  { label: string; variant: "success" | "warning" | "destructive" }
> = {
  booked: { label: "Booked", variant: "success" },
  rescheduled: { label: "Rescheduled", variant: "warning" },
  cancelled: { label: "Cancelled", variant: "destructive" },
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
