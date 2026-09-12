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
        {/* Signal & Depth PR-8 — each row is items-start, not items-center,
            for the same reason as hero.tsx's Assisted-Mode line: at 360px
            the two-column grid leaves "Professional Services" too little
            room, it wraps, and items-center then centred the briefcase icon
            in the gutter between its two lines. Verified against real
            device-emulated renders: this wraps at 360 only — 390, 430, 768
            and landscape all keep it on one line, where items-start +
            mt-0.5 is pixel-identical to items-center (20px line-height,
            16px icon → a 2px offset either way). */}
        <ul className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 sm:flex sm:flex-wrap sm:items-center sm:justify-center sm:gap-x-8 sm:gap-y-3">
          {INDUSTRIES.map((industry) => (
            <li key={industry.label} className="flex items-start justify-center gap-2 sm:justify-start">
              <industry.icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="text-sm text-muted-foreground">{industry.label}</span>
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  );
}
