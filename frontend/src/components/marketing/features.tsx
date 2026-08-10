import {
  BookOpen,
  CalendarClock,
  CheckCheck,
  Inbox,
  ShieldAlert,
  Target,
} from "lucide-react";
import { Reveal } from "@/components/marketing/reveal";
import { SectionHeader } from "@/components/marketing/section-header";

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
      "No back-and-forth to find a time that works. HIRA Calendar checks real availability and books, reschedules, or cancels — no setup required, with optional Google Calendar sync.",
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

// V4 "Signal & Quiet": the 3x2 icon-card grid was the single most generic
// "SaaS feature grid" moment on the page (and, post-V3, visually identical
// to Problem's cards) — cut in favor of a spec-sheet list, a label column
// against a description column separated by hairline rules, no
// border/shadow/radius per row. Same six claims, same order; only the
// container disappears.
//
// Post-launch self-critique: at py-8/py-10 per row, six rows made this the
// single longest scroll on the page for what is, relatively, its least
// dense content — a "spacious" list had drifted into "slow." Rows tightened
// to py-6/py-7 (outer section padding untouched, still the shared Standard
// tier) — reads as a fast, scannable spec sheet again instead of a second
// hero-length section.
export function Features() {
  return (
    <section id="features" className="scroll-mt-16 border-t py-20 sm:py-28">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader title="Everything the front desk does, minus the wait" className="mx-auto max-w-2xl" />
        <div className="mt-16 divide-y divide-border border-t sm:mt-20">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="grid gap-3 py-6 sm:grid-cols-[16rem_1fr] sm:items-baseline sm:gap-10 sm:py-7"
            >
              <div className="flex items-center gap-3">
                <feature.icon className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <h3 className="text-lg font-semibold tracking-tight">{feature.title}</h3>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
