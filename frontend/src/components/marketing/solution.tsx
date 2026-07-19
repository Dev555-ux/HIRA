// The three-card breakdown of what "one employee" means (knowledge, calendar,
// hand-off) used to live here — it's cut because Features below covers the
// same three claims as concrete product capabilities. This section's only
// job is the thesis statement that frames Features; it should not re-list it.
export function Solution() {
  return (
    <section className="py-16 sm:py-20">
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight">
          One employee, not a bundle of bots
        </h2>
        <p className="mt-4 text-lg text-muted-foreground">
          A single AI agent holds the conversation, your calendar, and your
          leads together — not three separate tools handing your customer
          between them, and never pretending to know things it doesn&apos;t.
        </p>
      </div>
    </section>
  );
}
