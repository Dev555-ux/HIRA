import { Reveal } from "@/components/marketing/reveal";

// The three-card breakdown of what "one employee" means (knowledge, calendar,
// hand-off) used to live here — it's cut because Features below covers the
// same three claims as concrete product capabilities. This section's only
// job is the thesis statement that frames Features; it should not re-list it.
//
// V4 "Signal & Quiet": this is the page's first Signal band — the one
// non-negotiable claim the whole product rests on gets pulled out of the
// shared quiet/editorial register (no SectionHeader, no border-t) into a
// full-bleed inverted surface. bg-primary/text-primary-foreground are the
// same tokens every other dark-on-light pairing already uses, so this
// still inverts correctly in dark mode (primary flips light-on-dark there),
// not a new color. The hard color change is the section boundary — a
// hairline border on top of it would be redundant. "One employee" is the
// one phrase pulled into brand color: the single saturated accent earning
// its keep on the page's single most dominant moment, not sprinkled
// everywhere. No card, no icon grid: the previous three-card breakdown of
// this claim was cut for the same reason stated above, and reintroducing
// any container here would undercut the one thing this band should feel
// like — a statement, not a feature.
//
// Post-launch self-critique: the headline was too close in size to every
// quiet section's SectionHeader (type-display-lg tops out at 44px) — the
// color-invert was doing all the "this is the dominant section" work,
// typography wasn't. Pushed a full tier larger (matching Hero's own scale
// more closely, not FinalCta's — see final-cta.tsx for why the two Signal
// bands now read as unequal in weight on purpose) so the dominance survives
// even in grayscale, not just in color.
export function Solution() {
  return (
    <section className="bg-primary py-24 text-primary-foreground sm:py-32 lg:py-40">
      <Reveal className="mx-auto max-w-4xl px-4 text-center sm:px-6">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-foreground/50">
          The thesis
        </p>
        <h2 className="mx-auto mt-6 max-w-3xl text-balance text-5xl font-black tracking-tighter sm:text-6xl lg:text-7xl">
          <span className="text-brand">One employee</span>, not a bundle of
          bots
        </h2>
        <p className="mx-auto mt-6 max-w-xl text-pretty text-lg text-primary-foreground/70 sm:text-xl">
          A single AI agent holds the conversation, your calendar, and your
          leads together — not three separate tools handing your customer
          between them, and never pretending to know things it doesn&apos;t.
        </p>
      </Reveal>
    </section>
  );
}
