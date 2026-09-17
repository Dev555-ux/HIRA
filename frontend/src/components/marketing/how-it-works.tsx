import { Reveal } from "@/components/motion/reveal";
import { SectionHeader } from "@/components/marketing/section-header";

// V4 "Signal & Quiet": no more boxed cards — a connected numbered timeline
// instead, the numerals themselves carrying the sequence rather than a
// card boundary around each step.
//
// Post-launch self-critique: the first pass only drew the connecting line
// at lg (4-col row) and showed a bare, lineless 2x2 grid at sm/md — an
// unexplained middle state, not a considered one, for the exact breakpoint
// range ("each breakpoint should feel intentionally crafted") this
// component was supposed to prove out. Restructured instead of patched:
// single column with a continuous VERTICAL line through the numerals from
// mobile through tablet (a real timeline, not an absent one), switching to
// the 4-across horizontal line only at lg where a single row actually
// exists to connect.
//
// Final-review self-critique: even fixed, this stayed the most generic
// section on the page — four neutral numbered circles read as stock
// "onboarding steps" UI, the one component never pulled into the page's
// own accent system (Solution has the brand-colored phrase, FinalCta has
// the brand button). Numerals now use brand fill — the same restrained
// "progress/sequence marker" use hira-design already grants the
// active-nav indicator — so this section reads as HIRA's own, not a
// generic template's.

const STEPS = [
  {
    step: "1",
    title: "Teach it your business",
    description:
      "Import your website or write FAQs so HIRA can answer from information you actually provided.",
  },
  {
    step: "2",
    title: "Connect WhatsApp",
    description: "Link the WhatsApp Business number your customers already message.",
  },
  {
    step: "3",
    title: "Test it yourself",
    description:
      "Try real conversations in Demo Chat before a single customer sees a reply.",
  },
  {
    step: "4",
    title: "Go live, at your pace",
    description:
      "Start in Assisted Mode reviewing every reply, then switch a business to Autonomous once you trust it.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-16 border-t bg-secondary/40 py-20 sm:py-28">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <SectionHeader title="Set up in four steps" className="mx-auto max-w-2xl" />
        <ol className="relative mt-16 flex flex-col gap-10 lg:grid lg:grid-cols-4 lg:gap-x-8 lg:gap-y-10">
          <div
            className="absolute inset-y-0 left-[1.125rem] w-px bg-border lg:hidden"
            aria-hidden="true"
          />
          <div
            className="absolute inset-x-0 top-[1.125rem] hidden h-px bg-border lg:block"
            aria-hidden="true"
          />
          {STEPS.map((item) => (
            <li key={item.step} className="relative pl-14 lg:pl-0">
              <span className="absolute left-0 top-0 z-10 flex size-9 items-center justify-center rounded-full bg-brand text-sm font-semibold text-brand-foreground lg:static">
                {item.step}
              </span>
              <h3 className="mt-5 text-lg font-semibold tracking-tight">{item.title}</h3>
              <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
                {item.description}
              </p>
            </li>
          ))}
        </ol>
      </Reveal>
    </section>
  );
}
