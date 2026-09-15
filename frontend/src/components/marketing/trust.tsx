import { CheckCircle2 } from "lucide-react";
import { Reveal } from "@/components/marketing/reveal";

// Deliberately lightweight — a scannable checklist, not another card grid
// (Features below already covers these in depth). No logos, no testimonials:
// every line here is true of the product today, not a roadmap claim.
//
// V4 "Signal & Quiet": this is the page's quietest moment on purpose — no
// border, smaller type, muted color throughout. It should read as a
// footnote trailing off the SignatureDemo proof above it, not its own
// announced section, so the hierarchy has somewhere to recede to.
//
// Post-launch self-critique: the first pass went from text-sm to text-xs
// (12px) — past "quiet" into "you'll miss it," and 12px muted-on-muted is a
// legibility risk this page shouldn't take for four claims doing real work.
// Back to text-sm; still no border, still the smallest heading-less section
// on the page, still recedes — just readable while doing it.
const TRUST_ITEMS = [
  "Replies automatically",
  "Books appointments",
  "Uses your Business Knowledge",
  "Escalates to humans",
];

export function Trust() {
  return (
    <section className="py-6 sm:py-8">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 className="sr-only">What HIRA does today</h2>
        <ul className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-muted-foreground sm:justify-between">
          {TRUST_ITEMS.map((item) => (
            <li key={item} className="flex items-center gap-1.5 font-medium">
              <CheckCircle2 className="size-3.5 shrink-0 text-success" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  );
}
