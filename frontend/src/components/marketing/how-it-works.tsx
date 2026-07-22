import { cardClassName } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { SectionHeader } from "@/components/marketing/section-header";

// Steps stay <li> inside an <ol> (correct semantics for an ordered
// sequence) rather than the shared <Card> component, which always renders
// a <div> — Card has no asChild/polymorphic-tag support (unlike Button),
// and it's used across the whole dashboard, so it isn't touched here.
// Reusing its exported class string keeps this visually identical to
// every other card on the page without duplicating (and risking drifting
// from) the literal class list by hand.

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
    <section id="how-it-works" className="scroll-mt-16 border-t bg-secondary/40 py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader title="Set up in four steps" className="mx-auto max-w-2xl" />
        <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((item) => (
            <li key={item.step} className={cn(cardClassName, "p-6")}>
              <span className="flex size-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                {item.step}
              </span>
              <h3 className="mt-4 text-base font-semibold">{item.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{item.description}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
