import {
  BookOpen,
  CalendarClock,
  CheckCheck,
  Inbox,
  ShieldAlert,
  Target,
} from "lucide-react";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeader } from "@/components/marketing/section-header";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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

// Sprint 66 PR-6 — "Signal & Quiet"'s spec-sheet list (V4, see prior history
// in git blame) becomes a Bento grid: same six claims, same order, same
// data — only the container and its per-card visual weight change. Applied
// by array index, not by reordering FEATURES: Knowledge base(0),
// Appointment booking(1), and Unified inbox(5) get the wide/full-width grid
// spans and the larger icon/type/padding treatment the ticket asks for;
// Assisted or Autonomous(2), Escalation(3), and Lead pipeline(4) stay
// compact. Spans only apply at `lg:` — sm is a plain balanced 2-up grid,
// and mobile is simple stacked single-column cards, per the brief.
//
// Cards reuse <Card> verbatim (existing radius/shadow/elevation) — no new
// card treatment, no glassmorphism, no gradients. T4.1 dropped `interactive`:
// the hover lift it added promised a click these cards do not accept
// (DESIGN-MOTION-001 §5.2 — only clickable cards move). Still pure CSS, still
// no client state and no "use client" anywhere in this file.
const LARGE_FEATURE_INDICES = new Set([0, 1, 5]);
const LARGE_SPAN_CLASS_NAME: Record<number, string> = {
  0: "lg:col-span-2",
  5: "lg:col-span-3",
};

export function Features() {
  return (
    <section id="features" className="scroll-mt-16 border-t py-20 sm:py-28">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <SectionHeader title="Everything the front desk does, minus the wait" className="mx-auto max-w-2xl" />
        {/* Sprint 66 PR-9 — <ul>/<li>, not a bare grid of <div>s: a real set
            of items, matching the list convention Journey and HeroTrustStrip
            already use for their own multi-item content. No visual change —
            Tailwind's preflight already zeroes list-style/margin on every
            <ul>/<ol> in this app (see Journey's own unnumbered <ol>). */}
        <ul className="mt-16 grid gap-4 sm:mt-20 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3">
          {FEATURES.map((feature, index) => {
            const large = LARGE_FEATURE_INDICES.has(index);
            return (
              <li key={feature.title} className={LARGE_SPAN_CLASS_NAME[index]}>
                {/* Phase 2 — glass, and a hairline the flat card never had. Card's
                    own `shadow-e2` on a flat fill was the page's only
                    elevation language below the hero, where every raised
                    surface is a bordered translucent one. This is a card, a
                    surface the brief names as a good glass candidate — not a
                    large panel or a decorative blur. */}
                <Card
                  className={cn(
                    "glass-flat flex h-full flex-col gap-3 border border-[color:var(--glass-border)]",
                    large ? "p-6 sm:p-8" : "p-5 sm:p-6",
                  )}
                >
                  <feature.icon
                    className={cn("shrink-0 text-muted-foreground", large ? "size-6" : "size-5")}
                    aria-hidden="true"
                  />
                  <h3 className={cn("font-semibold tracking-tight", large ? "text-xl" : "text-lg")}>
                    {feature.title}
                  </h3>
                  <p className={cn("leading-relaxed text-muted-foreground", large ? "text-base" : "text-sm")}>
                    {feature.description}
                  </p>
                </Card>
              </li>
            );
          })}
        </ul>
      </Reveal>
    </section>
  );
}
