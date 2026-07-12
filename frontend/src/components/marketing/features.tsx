import {
  BookOpen,
  CalendarClock,
  CheckCheck,
  Inbox,
  ShieldAlert,
  Target,
} from "lucide-react";

const FEATURES = [
  {
    icon: BookOpen,
    title: "Knowledge base",
    description:
      "Import your website or write FAQs directly. HIRA retrieves the relevant answer for every question instead of improvising.",
  },
  {
    icon: CalendarClock,
    title: "Appointment booking",
    description:
      "Checks real availability and books, reschedules, or cancels appointments in your connected Google Calendar.",
  },
  {
    icon: CheckCheck,
    title: "Assisted or Autonomous",
    description:
      "Review and approve every AI reply and booking before it goes out, or switch a business to fully autonomous once you trust it.",
  },
  {
    icon: ShieldAlert,
    title: "Escalation to a human",
    description:
      "Uncertain or sensitive conversations are flagged and handed to a person instead of the AI guessing.",
  },
  {
    icon: Target,
    title: "Lead pipeline",
    description:
      "Every conversation that looks like a lead is tracked through a pipeline — new, contacted, qualified, won — automatically or added by hand.",
  },
  {
    icon: Inbox,
    title: "Unified inbox",
    description:
      "Every customer conversation, appointment, and lead lives in one dashboard — nothing tracked in a separate spreadsheet.",
  },
];

export function Features() {
  return (
    <section id="features" className="scroll-mt-16 border-t py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight">Everything the front desk does, minus the wait</h2>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="rounded-xl border bg-card p-6">
              <feature.icon className="size-5 text-muted-foreground" aria-hidden="true" />
              <h3 className="mt-4 text-base font-semibold">{feature.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
