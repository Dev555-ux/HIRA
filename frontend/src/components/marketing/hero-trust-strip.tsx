import { Briefcase, Building2, Dumbbell, Scissors, Stethoscope, UtensilsCrossed } from "lucide-react";
import { Reveal } from "@/components/marketing/reveal";

// Sprint 66 PR-7 — a fast answer to "who is this built for," not a
// testimonial or logo cloud: no customer names, no claimed counts, nothing
// that could go stale. Deliberately quiet — no pill/border/card per item,
// just an icon-label pair, the same restraint Trust (below, in the page)
// already applies to its own claims.
const INDUSTRIES = [
  { icon: Stethoscope, label: "Dental Clinics" },
  { icon: Scissors, label: "Salons & Spas" },
  { icon: Dumbbell, label: "Fitness Studios" },
  { icon: UtensilsCrossed, label: "Restaurants" },
  { icon: Building2, label: "Real Estate" },
  { icon: Briefcase, label: "Professional Services" },
];

// A real <ul> (semantic list, not a styled row of <div>s) — screen readers
// announce "list, 6 items." Icons are aria-hidden; the label text alone
// carries the content. border-t (not border-b) matches every other
// section's own convention of owning its top divider — SignatureDemo right
// below already opens with border-t, so this needs no bottom rule of its
// own to avoid a doubled line between them.
export function HeroTrustStrip() {
  return (
    <section className="border-t py-10 sm:py-12">
      <Reveal className="mx-auto max-w-4xl px-4 text-center sm:px-6">
        <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Built for
        </span>
        <ul className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 sm:flex sm:flex-wrap sm:items-center sm:justify-center sm:gap-x-8 sm:gap-y-3">
          {INDUSTRIES.map((industry) => (
            <li key={industry.label} className="flex items-center justify-center gap-2 sm:justify-start">
              <industry.icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="text-sm text-muted-foreground">{industry.label}</span>
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  );
}
