const FAQS = [
  {
    question: "Is HIRA a chatbot?",
    answer:
      "No. A chatbot answers messages and stops there. HIRA is an AI employee — it holds the whole job: the conversation, your calendar, and your leads, together, grounded in what you've told it about your business.",
  },
  {
    question: "Does HIRA reply to my customers automatically?",
    answer:
      "It depends on the mode you choose. In Assisted Mode — the default — HIRA drafts every reply and proposed booking, and you approve, edit, or reject it before anything is sent. In Autonomous Mode, HIRA sends replies and makes bookings on its own. Most businesses start in Assisted Mode and move to Autonomous once they trust the AI's replies.",
  },
  {
    question: "What happens if HIRA doesn't know the answer?",
    answer:
      "It escalates the conversation to a human instead of guessing. Escalated conversations are flagged clearly in your dashboard so nothing gets missed.",
  },
  {
    question: "Can it actually book appointments?",
    answer:
      "Yes — HIRA connects to your Google Calendar, checks real availability, and can book, reschedule, or cancel appointments as part of the conversation.",
  },
  {
    question: "Do I need a WhatsApp Business account already?",
    answer:
      "Yes. HIRA connects to a WhatsApp Business number you already have — it doesn't create one for you.",
  },
  {
    question: "Is my business's data separated from other businesses using HIRA?",
    answer:
      "Yes. Every business's conversations, customers, and knowledge base are isolated from every other business on the platform.",
  },
  {
    question: "What does HIRA cost?",
    answer:
      "Pricing isn't public yet. Sign up to get started, or reach out once you're in the dashboard.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="scroll-mt-16 py-16 sm:py-24">
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <h2 className="text-center text-3xl font-semibold tracking-tight">Frequently asked questions</h2>
        <div className="mt-10 space-y-3">
          {FAQS.map((faq) => (
            <details key={faq.question} className="group rounded-xl border bg-card px-6 py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-semibold marker:content-none">
                {faq.question}
                <span
                  aria-hidden="true"
                  className="shrink-0 text-lg leading-none text-muted-foreground transition-transform group-open:rotate-45"
                >
                  +
                </span>
              </summary>
              <p className="mt-3 text-sm text-muted-foreground">{faq.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
