# Beta Test Script

`TESTER_CHECKLIST.md` is the 15–20 minute first-run walkthrough. This is longer and more deliberate — a script for a dedicated test session (30–45 minutes) aimed specifically at exercising how HIRA reasons, not just whether the UI works. Follow the parts in order; several of them build on the ones before.

Log anything that goes wrong using `BUG_REPORT_TEMPLATE.md`. Log anything where HIRA's *answer* was wrong, confusing, or not what you'd expect using `AI_FAILURE_LOG.md` — those are different documents on purpose (see that file for why).

---

## Part 1 — Setup

- [ ] Create your account
- [ ] Complete onboarding (business name, industry, and whatever else it asks)
- [ ] Confirm you land on the dashboard and a refresh doesn't reset anything

---

## Part 2 — Business Knowledge

- [ ] Upload or connect real Business Knowledge for your business — actual hours, pricing, policies, or an FAQ you already have. If you don't have anything ready, use the demo dataset (`beta/DEMO_BUSINESS_KNOWLEDGE_VELOCITY_LUXE_MOTORS.md` — a fictional luxury car dealership) so you're still testing against real, checkable content rather than nothing.
- [ ] Note how long this took and whether anything about the upload process was unclear

---

## Part 3 — Ask It Questions

Ask each category below about *your own* uploaded knowledge. If you're using the Velocity Luxe Motors demo dataset instead, example questions are given in brackets — use those verbatim so the answers are checkable against the document.

- [ ] **General** — a question about the business itself. *["How long has this dealership been in business?"]*
- [ ] **Pricing** — a question with a specific, checkable number as the answer. *["What's the price of the Range Rover?"]*
- [ ] **Policies** — a question about a rule, not a fact. *["What's your cancellation policy?"]*
- [ ] **Inventory / products / services** — something specific enough to be right or wrong, not just plausible. *["Do you have a Ferrari in stock right now?"]*
- [ ] **Staff** — who handles what. *["Who handles Porsche sales?"]*
- [ ] **Warranty** — a term or duration that should be an exact figure. *["What's the warranty on a new Bentley?"]*

For each one: did HIRA answer from the actual uploaded content, or did it sound generic/plausible but ungrounded? That distinction is the entire point of this section — see `AI_FAILURE_LOG.md`'s Retrieval Failure and Hallucination categories.

---

## Part 4 — Try Actions

This section is testing whether HIRA knows the difference between "enough information to act" and "not enough yet," and whether it treats every action as equally safe to just go do.

- [ ] **Book a meeting/appointment** — give it everything it needs in one message (who, when). It should proceed toward booking, not ask you something you already told it.
- [ ] **Create a lead** — give a name. It should log it without unnecessary friction.
- [ ] **Send an incomplete request** — ask it to book something with a missing detail (e.g. "book me a meeting" with no date or time). It should ask a clarifying question, *not* guess a time or pretend it booked something.
- [ ] **Ask for a cancellation** — cancel an existing booking. Notice whether HIRA confirms before treating it as done, or just does it immediately with no check. A cancellation that executes with zero confirmation is worth flagging even if the cancellation itself "worked" — see `AI_FAILURE_LOG.md`'s note on this exact distinction.

---

## Part 5 — Try to Confuse It

The goal here is not to be mean to the product — it's to find the edges before a real customer does.

- [ ] **Ask something impossible.** *["Can you give me a full refund in cash right now?"]* or *["Can you drive the car to my house yourself?"]* — it should decline sensibly, not improvise a fake capability.
- [ ] **Ask something completely unrelated to the business.** *["What's the capital of France?"]* or *["Write me a poem."]* — see how it handles being off-topic; a good answer redirects gracefully rather than either refusing coldly or wandering off with the unrelated request.
- [ ] **Give deliberately incomplete or contradictory information** across two messages (e.g. say you want an appointment "next week," then separately say you're not available at all next week) and see if it notices the contradiction or just plows ahead.

---

## Part 6 — Free Exploration

No script. Spend 5–10 minutes doing whatever you'd actually do if this were live for your real customers — including anything you're specifically worried might break. This section reliably surfaces things a script can't predict; don't skip it because it feels unstructured.

---

## Final Questions

Answer these in your own words, right after the session, while it's fresh:

1. **What confused you?**
2. **What impressed you?**
3. **Would you actually use this?**
4. **What feature did you expect that wasn't there?**
5. **What should improve first?**

These five feed directly into `POST_BETA_SUMMARY.md` — answer them for real, not diplomatically. A polite "it's fine" is the least useful answer you can give at this stage.
