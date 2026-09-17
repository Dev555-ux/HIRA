import { MessageCircle, Share2, Sparkles, TrendingUp, Zap } from "lucide-react";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeader } from "@/components/marketing/section-header";

const JOURNEY = [
  {
    step: "01",
    icon: MessageCircle,
    title: "WhatsApp arrives",
    description:
      "The customer messages your existing WhatsApp Business number — no app to install, no new number to give out.",
  },
  {
    step: "02",
    icon: Sparkles,
    title: "HIRA reads it",
    description:
      "It pulls out what actually matters — the service, the day, the urgency — the way a person reading the chat would.",
  },
  {
    step: "03",
    icon: Share2,
    title: "Checks what it needs to",
    description: "Your calendar, your knowledge base, the customer's history — before it ever answers.",
  },
  {
    step: "04",
    icon: Zap,
    title: "Acts on it",
    description:
      "Books the appointment, answers from what you've told it, or hands off to your team — whichever the moment calls for.",
  },
  {
    step: "05",
    icon: TrendingUp,
    title: "Nothing goes cold",
    description:
      "Every conversation is tracked automatically, so no lead sits unanswered and no follow-up gets forgotten.",
  },
];

// Sprint 66 — explains the mechanism (the "how") right after SignatureDemo
// proves the outcome (the "what"), before Problem makes the deeper case.
// Deliberately not How It Works' filled-numeral timeline: that pattern is
// spoken for two sections later and covers user *setup* steps, not a single
// message's *runtime* path. A bare hairline icon plus a small numbered
// eyebrow carries the sequence instead — Problem's quiet icon-column
// language plus Solution's eyebrow-label styling, not a new pattern.
// <ol>/<li> (not Problem's plain <div> grid): this content is a genuine
// ordered sequence, so screen readers should announce it as one.
export function Journey() {
  return (
    <section id="journey" className="scroll-mt-16 border-t py-20 sm:py-28">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <SectionHeader
          title="From a message to a finished job"
          description="What happens between a customer texting and the job being done."
          className="mx-auto max-w-2xl"
        />
        <ol className="mt-16 grid gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-5">
          {JOURNEY.map((item) => (
            <li key={item.step}>
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground/70">
                {item.step}
              </span>
              <div className="mt-3 glass-flat flex size-10 items-center justify-center rounded-xl border border-[color:var(--glass-border)]">
                <item.icon className="size-4 text-muted-foreground" aria-hidden="true" />
              </div>
              {/* Phase 2 — lg:min-h reserves the two lines the longest title needs,
                  so all five descriptions start on one baseline. Only at lg:
                  below it the grid is 1-2 columns and titles wrap
                  unpredictably, where a reserved height would just add gaps. */}
              <h3 className="mt-5 text-lg font-semibold tracking-tight lg:min-h-[3.3rem]">
                {item.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{item.description}</p>
            </li>
          ))}
        </ol>
      </Reveal>
    </section>
  );
}
