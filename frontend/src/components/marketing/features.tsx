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
      "Every answer comes from what you've actually told HIRA — imported from your website or written as FAQs — never a generic guess.",
  },
  {
    icon: CalendarClock,
    title: "Appointment booking",
    description:
      "No back-and-forth to find a time that works. HIRA checks real availability and books, reschedules, or cancels in your connected Google Calendar.",
  },
  {
    icon: CheckCheck,
    title: "Assisted or Autonomous",
    description:
      "You stay in control for as long as you want — review every reply and booking, or switch to fully autonomous once you trust it.",
  },
  {
    icon: ShieldAlert,
    title: "Escalation to a human",
    description:
      "Customers never get stuck with a guess. Uncertain or sensitive conversations are flagged and handed to a person on your team.",
  },
  {
    icon: Target,
    title: "Lead pipeline",
    description:
      "No lead falls through the cracks. Every conversation that looks like one is tracked automatically — new, contacted, qualified, won.",
  },
  {
    icon: Inbox,
    title: "Unified inbox",
    description:
      "One place for the whole customer relationship — every conversation, appointment, and lead, with nothing lost in a separate spreadsheet.",
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
