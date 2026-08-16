import { CalendarClock } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/ui/status-pill";
import { APPOINTMENT_STATUS, APPOINTMENT_STATUS_BADGE, formatAppointmentRange } from "@/lib/appointments";
import type { Appointment } from "@/lib/types";
import { cn } from "@/lib/utils";

function customerLabel(customer: { display_name: string | null; wa_phone: string | null } | null): string {
  return customer?.display_name || customer?.wa_phone || "Unknown customer";
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", hour12: true });
}

// Dashboard V2's schedule — a real agenda (a time rail down the left, one
// row per real upcoming Appointment) instead of a table. Same
// `useAppointments({ from: now })` data V1 reads; only the presentation is
// new. Sprint 88 dogfooding: this was originally titled "Today's Business,"
// but `from: now` returns everything upcoming — in the seeded dataset that
// meant appointments 2-8 days out under a heading promising "today," which
// is exactly the kind of thing that's confusing without being wrong.
// Renamed rather than re-scoped to literally-today: most days won't have a
// same-day appointment, so an honest "Upcoming" is more useful than an
// empty "Today" most of the time.
export function SchedulePanel({ appointments }: { appointments: Appointment[] }) {
  return (
    <div className="flex h-full flex-col rounded-2xl bg-card p-6 shadow-e2 sm:p-7">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="type-title">Upcoming appointments</h2>
        <Button asChild size="sm" variant="ghost">
          <Link href="/appointments">View all</Link>
        </Button>
      </div>

      {appointments.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 py-8 text-center">
          <CalendarClock className="size-6 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">No upcoming appointments.</p>
          <Button asChild size="sm" variant="outline">
            <Link href="/appointments">New appointment</Link>
          </Button>
        </div>
      ) : (
        <ol className="relative space-y-5">
          <div className="absolute bottom-2 left-[2.6rem] top-2 w-px bg-border" aria-hidden="true" />
          {appointments.slice(0, 5).map((appt) => {
            const badge = APPOINTMENT_STATUS_BADGE[appt.status];
            const name = customerLabel(appt.customer);
            return (
              <li key={appt.id} className="relative flex items-start gap-4">
                <span className="w-16 shrink-0 pt-1 text-right text-xs font-medium tabular-nums text-muted-foreground">
                  {timeLabel(appt.starts_at)}
                </span>
                <span
                  className={cn(
                    "relative z-10 mt-1 flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary ring-4 ring-card",
                  )}
                >
                  {initials(name)}
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-medium">{name}</p>
                    <StatusPill state={APPOINTMENT_STATUS[appt.status]} className="shrink-0">
                      {badge.label}
                    </StatusPill>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {formatAppointmentRange(appt.starts_at, appt.ends_at)}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
