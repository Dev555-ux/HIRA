import { Clock, MessageSquareOff, Users } from "lucide-react";
import { Reveal } from "@/components/marketing/reveal";
import { SectionHeader } from "@/components/marketing/section-header";

const PROBLEMS = [
  {
    icon: Clock,
    title: "Customers message outside business hours",
    description:
      "A question at 9pm sits unanswered until morning — and by then, they've often already messaged someone else.",
  },
  {
    icon: MessageSquareOff,
    title: "Every reply competes with running the business",
    description:
      "Answering the same questions about hours, pricing, and availability takes time away from the customers already in front of you.",
  },
  {
    icon: Users,
    title: "Leads and follow-ups fall through the cracks",
    description:
      "Without a system tracking every conversation, it's easy to lose track of who still needs a reply, a booking, or a follow-up.",
  },
];

// V4 "Signal & Quiet": this is quiet-register content — the noise before
// the thesis (Solution, below) resolves it — so it drops the card grid
// entirely. Three bare columns, no border/shadow/radius, separated by
// whitespace alone. bg-secondary/40 + border-t stay: unlike Solution's hard
// color invert, this is a soft tonal shift that still benefits from a
// hairline marking where it starts.
//
// Post-launch self-critique: a fully bare icon with no chip at all, next to
// bold 18px headings, read as thin/incidental rather than quiet-by-design.
// A hairline ring (outline only, no fill) gives it presence without
// reintroducing the filled bg-muted chip that made this read as a card
// again — same "no fill, hairline does the work" language the rest of the
// page's dividers already use.
export function Problem() {
  return (
    <section className="border-t bg-secondary/40 py-20 sm:py-28">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader
          title="WhatsApp is where your customers already are — and where they expect a fast reply"
          className="mx-auto max-w-2xl"
        />
        {/* Sprint 66 PR-10 — <ul>/<li>, not bare <div>s: matches the
            semantic-list convention Journey/HeroTrustStrip/Features already
            use. Zero visual change — Tailwind's preflight already zeroes
            list-style/margin on every <ul> here (see Journey's own
            unnumbered <ol>). */}
        <ul className="mt-16 grid gap-x-8 gap-y-12 sm:grid-cols-3">
          {PROBLEMS.map((problem) => (
            <li key={problem.title}>
              <div className="flex size-10 items-center justify-center rounded-full border border-border">
                <problem.icon className="size-4 text-muted-foreground" aria-hidden="true" />
              </div>
              <h3 className="mt-5 text-lg font-semibold tracking-tight">{problem.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {problem.description}
              </p>
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  );
}
