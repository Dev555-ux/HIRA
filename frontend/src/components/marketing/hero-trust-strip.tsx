import { Briefcase, Building2, Dumbbell, Scissors, Stethoscope, UtensilsCrossed } from "lucide-react";

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

// Cinematic rebuild — this was a full-width <section> of its own directly
// below the hero ("Built for", icon + label pairs, no chrome). It is now a
// block inside the hero's copy rail, styled as the reference's enclosed
// pills. One thing deliberately did NOT come across from the reference: its
// labels are hardcoded white on a dark-only page, where these stay on
// tokens so the pills work in both themes.
//
// Liquid Glass PR-1 — these pills previously refused backdrop blur on the
// grounds that it "buys nothing over an opaque background." That was true
// when it was written and is not true now: PR-1 moved the hero's key light
// so the bloom's near edge passes behind this exact block, and the pills sit
// on a lit gradient rather than flat --background. The material samples it —
// which is also why the saturation boost matters more here than the blur
// radius does. Cost is bounded and one-time: the backdrop behind them is
// static (the hero light does not animate), so each pill composites once and
// caches rather than re-filtering per frame the way the sticky header does.
//
// Still a real <ul> (semantic list, not a styled row of <div>s) — screen
// readers announce "list, 6 items." Icons are aria-hidden; the label text
// alone carries the content.
export function HeroTrustPills() {
  return (
    <>
      <span className="text-[0.6875rem] font-bold uppercase tracking-[0.12em] text-muted-foreground">
        Trusted by modern businesses
      </span>
      {/* items-center is safe here in a way it was not in the old
          full-width section: each label now sits in its own shrink-wrapped
          pill rather than a two-column grid cell, so "Professional
          Services" can no longer wrap mid-pill and strand the icon in the
          gutter between two lines — which is exactly what PR-8's
          items-start + mt-0.5 was working around. The pill wraps as a unit
          instead. */}
      <ul className="mt-2.5 flex flex-wrap justify-center gap-2 lg:justify-start">
        {INDUSTRIES.map((industry) => (
          <li
            key={industry.label}
            className="glass flex items-center gap-1.5 rounded-full border border-[color:var(--glass-border)] px-3 py-1"
          >
            <industry.icon className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span className="text-xs font-medium text-muted-foreground">{industry.label}</span>
          </li>
        ))}
      </ul>
    </>
  );
}
