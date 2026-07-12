import { BookOpen, CalendarClock, UserCheck } from "lucide-react";

const PILLARS = [
  {
    icon: BookOpen,
    title: "Grounded in your own knowledge",
    description:
      "Import your website, FAQs, or notes into HIRA's knowledge base. It answers from what you've actually told it — not a generic script.",
  },
  {
    icon: CalendarClock,
    title: "Books directly into your calendar",
    description:
      "HIRA checks real availability and books, reschedules, or cancels appointments in your connected Google Calendar — no back-and-forth.",
  },
  {
    icon: UserCheck,
    title: "Knows when to hand off to you",
    description:
      "When a conversation needs a human — a complaint, an unusual request, anything outside its knowledge — HIRA escalates it instead of guessing.",
  },
];

export function Solution() {
  return (
    <section className="py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight">
            One AI receptionist, working inside WhatsApp
          </h2>
          <p className="mt-4 text-muted-foreground">
            HIRA connects to your business&apos;s WhatsApp number and takes on the
            parts of customer conversation that are repetitive and time-sensitive
            — without pretending to know things it doesn&apos;t.
          </p>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {PILLARS.map((pillar) => (
            <div key={pillar.title} className="rounded-xl border bg-card p-6">
              <div className="flex size-10 items-center justify-center rounded-full bg-primary/10">
                <pillar.icon className="size-5 text-primary" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold">{pillar.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{pillar.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
