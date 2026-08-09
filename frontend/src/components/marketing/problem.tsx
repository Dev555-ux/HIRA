import { Clock, MessageSquareOff, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Reveal } from "@/components/marketing/reveal";
import { SectionHeader } from "@/components/marketing/section-header";

const PROBLEMS = [
  {
    icon: Clock,
    title: "Customers message outside business hours",
    description:
      "A question at 9pm sits unanswered until morning — and by then, they've often already messaged someone else.",
  },
  {
    icon: MessageSquareOff,
    title: "Every reply competes with running the business",
    description:
      "Answering the same questions about hours, pricing, and availability takes time away from the customers already in front of you.",
  },
  {
    icon: Users,
    title: "Leads and follow-ups fall through the cracks",
    description:
      "Without a system tracking every conversation, it's easy to lose track of who still needs a reply, a booking, or a follow-up.",
  },
];

export function Problem() {
  return (
    <section className="border-t bg-secondary/40 py-16 sm:py-24">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader
          title="WhatsApp is where your customers already are — and where they expect a fast reply"
          className="mx-auto max-w-2xl"
        />
        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {PROBLEMS.map((problem) => (
            <Card key={problem.title} className="p-6">
              <div className="flex size-10 items-center justify-center rounded-full bg-muted">
                <problem.icon className="size-5 text-muted-foreground" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold">{problem.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{problem.description}</p>
            </Card>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
