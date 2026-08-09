import { CheckCircle2 } from "lucide-react";
import { Reveal } from "@/components/marketing/reveal";

// Deliberately lightweight — a scannable checklist, not another card grid
// (Features below already covers these in depth). No logos, no testimonials:
// every line here is true of the product today, not a roadmap claim.
const TRUST_ITEMS = [
  "Replies automatically",
  "Books appointments",
  "Uses your Business Knowledge",
  "Escalates to humans",
];

export function Trust() {
  return (
    <section className="border-t py-10 sm:py-12">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6">
        <h2 className="sr-only">What HIRA does today</h2>
        <ul className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 sm:justify-between">
          {TRUST_ITEMS.map((item) => (
            <li key={item} className="flex items-center gap-2 text-sm font-medium">
              <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  );
}
