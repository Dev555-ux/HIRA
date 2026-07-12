# HIRA Brand Bible

**Status**: Canonical. Every piece of external copy — marketing site, deck, job-posting-style feature announcements, README, social — should be checked against this document before it ships. If a page contradicts this file, the page is wrong, not the file (update whichever is stale in the same change, per `.claude/CLAUDE.md` §5).

**Grounding**: Every claim below is built from what's actually true today — `README.md`, `ARCHITECTURE.md`, `.claude/PROJECT_CONTEXT.md`, and the live codebase (511 backend tests, 145 frontend tests, one real test business, verified end-to-end against Meta's WhatsApp Cloud API and Google Calendar). Nothing here invents a capability, a customer, a number, or a quote that doesn't exist. Where this document describes the *vision* rather than the *product*, it says so explicitly, every time — matching the discipline `README.md` already holds itself to.

**The one thing to remember if you remember nothing else**: HIRA is not an AI receptionist. "AI receptionist" is a feature category — a crowded shelf of point tools that answer WhatsApp messages. HIRA is an AI employee. The Receptionist is its first job title, not its name.

---

## 1. One-Sentence Positioning

**HIRA is the AI employee businesses hire to answer customers, book appointments, and chase leads — not a chatbot they install and babysit.**

---

## 2. Elevator Pitch (30 seconds, ~80 words)

Most businesses that take appointments — clinics, salons, gyms — don't lose customers because they're bad at their job. They lose them because nobody's fast enough on WhatsApp, all day, every day. HIRA is an AI employee that takes that job over: it answers from your own knowledge, books straight into your calendar, and keeps every lead moving — with a human able to review or override anything it does. You're not configuring a chatbot. You're hiring your first employee that never clocks out.

---

## 3. Two-Minute Pitch (~320 words)

Small businesses that take appointments — clinics, salons, gyms, consultants — don't lose customers because they're bad at what they do. They lose them because nobody has time to answer WhatsApp instantly, keep the calendar straight, and follow up on every lead, all day, every day, without exception. The moment a reply is an hour late, that customer has usually already messaged someone else. Hiring a person for this doesn't scale with message volume, and ignoring WhatsApp isn't an option when that's where the customer already is.

HIRA is an AI employee that takes that job over. It answers customers from the business's own knowledge — never a guess about pricing, hours, or policy. It books straight into the connected Google Calendar. It logs every lead and moves it through a pipeline. And it does all of this as one system: one AI agent holding the conversation, the calendar, and the CRM together — not three separate bots handing a customer off between them.

It ships supervised. Every reply and every action sits in a dashboard for a human to approve, edit, reject, or escalate — Assisted Mode is the default for every business, on day one. Autonomous Mode exists once a business decides it's earned that trust; it's a choice the business makes, never one HIRA makes for itself.

This isn't a pitch for something we're planning to build. It's running: real WhatsApp conversations, verified against Meta's actual Cloud API; real calendar bookings against Google Calendar; over 650 automated tests across the backend and dashboard. What hasn't happened yet is deployment beyond one real test business — that's the next milestone, not a hypothesis.

The Receptionist is the first hire. The direction is more roles — sales follow-up, support — each proven the same way, one validated need at a time, building toward what we call the AI Business Operating System: a business hiring an AI workforce the way it hires a human one. We're not there. We're building the first employee properly, because the rest of that direction only means anything if the first hire actually works.

---

## 4. Mission

**HIRA exists to give small businesses their time back by taking over the one job that never stops and never scales on its own: answering customers, keeping the calendar straight, and following up on every lead — instantly, all day, without needing to hire, train, or manage a person to do it.**

---

## 5. Vision

We believe a small business should be able to hire the way a large one does — not just people, but employees: specialized, reliable AI hires that take over one job completely, prove themselves against a real business, and only then earn the next one.

HIRA started with a single hire: the Receptionist. The direction is a full AI workforce a business assembles one proven role at a time — not one assistant that tries to do everything and does none of it well.

We call the destination the **AI Business Operating System** — not because we've built it, but because it's the shape of where hiring your first AI employee eventually leads. Today, that destination is a direction, not a delivery date. The only role that exists is the Receptionist. Everything else — Sales, Support, whatever comes after — gets built only once a real business has proven it needs the next hire, the same discipline that built the first one.

---

## 6. Core Values

1. **Earn autonomy, don't assume it.** Every capability ships in Assisted Mode before it's ever allowed to act on its own. Trust is a milestone, not a default setting.
2. **Grounded over generic.** HIRA answers from what a business actually told it — never a plausible-sounding guess. An unknown answer becomes a handoff, not a hallucination.
3. **One employee, not a bundle of bots.** A single AI agent holds the whole conversation, the calendar, and the pipeline — because a customer doesn't experience a business as four separate tools, and neither should HIRA.
4. **Prove it before you build it.** Every new capability — a new mode, a new role, a new piece of infrastructure — ships after a real, validated need, not ahead of one.
5. **Boring where it counts.** The technology holding a business's customer relationships is not the place for novelty. Proven patterns, not resume-driven architecture.
6. **The owner stays the boss.** Automation that removes a human's ability to see, edit, or override what happened with their own customer is not automation HIRA will ship.

---

## 7. Brand Personality

If HIRA were a person, they'd be the operations hire every small business owner wishes they'd found sooner: unflappable under a flood of messages, exact about what they do and don't know, and allergic to overpromising. Competent enough to be trusted with the front desk on day one — and honest enough to say "let me get someone" the moment a conversation needs a person.

| We are | Not |
|---|---|
| Confident | Cocky |
| Precise | Clinical |
| Warm | Chatty |
| Direct | Blunt |
| Calm | Passive |
| Capable | Boastful |

---

## 8. Tone of Voice

- Write like you're explaining it to a smart friend who owns the business — not pitching a VC.
- Short sentences do the heavy lifting. Long sentences are earned, not the default.
- Say what it does, not what it "enables." *Books the appointment*, not *enables seamless appointment booking*.
- Contractions are normal speech. Use them.
- Never claim a number, a customer, or a result HIRA hasn't actually produced.
- Confidence comes from specificity, not adjectives. Replace "powerful," "smart," "seamless" with the actual mechanism.
- Humor is dry and rare, and never at the customer's expense.
- When in doubt, cut the sentence that describes a feeling and keep the one that describes a fact.

---

## 9. Messaging Guide

**Core message**: HIRA is the AI employee that takes over your front desk — answering, booking, and following up — grounded in your business, supervised by you, until you trust it enough not to be.

**Supporting pillars**:

| Pillar | Proof |
|---|---|
| One employee, not a bot bundle | One AI agent holds the conversation, the calendar, and the pipeline — not three tools handing a customer between them. |
| It only knows what you've told it | Answers come from your knowledge base, retrieved per message — not a guess, not the open internet. |
| You keep the keys | Assisted Mode by default, for every business, on day one. Autonomous Mode is a choice you make, not one HIRA makes for you. |
| It's where your customers already are | WhatsApp, not a new inbox to check. |

**By audience**:
- **Business owner** (primary): lead with time and lost customers — the cost of a slow reply, the lead that went cold.
- **Technical evaluator / investor**: lead with the architecture discipline — provider-agnostic (LLM, embeddings, and calendar all swappable), one system of record, real automated test coverage, one real business proven before scaling the model to more.

---

## 10. Taglines (20)

1. Hired, not installed.
2. The front desk that never clocks out.
3. Answers instantly. Escalates honestly.
4. Your first employee that runs on WhatsApp.
5. It only knows what you've told it — on purpose.
6. One employee. Every conversation, every booking, every lead.
7. The AI you manage, not the one you babysit.
8. Every message answered. Every lead followed up. Every night.
9. Built to be hired, not configured.
10. Not a chatbot. A hire.
11. Trust it in stages. It was built that way.
12. The employee that reads the whole file before it speaks.
13. No missed message. No dropped lead. No overtime.
14. Software waits to be used. HIRA shows up to work.
15. It answers like it's been there since day one.
16. The first hire in a company that never sleeps.
17. Grounded in your business. Not the internet's best guess.
18. Every customer gets your best answer, every time, instantly.
19. The receptionist job, done by an employee that never leaves.
20. Your front desk, staffed, on WhatsApp, right now.

---

## 11. Hero Headlines (30)

**Problem-led**
1. Your customers message at 9pm. Your front desk closes at 6.
2. Every slow reply on WhatsApp is a customer messaging someone else.
3. The lead you meant to follow up with went to whoever answered first.
4. Nobody has time to answer instantly, book perfectly, and follow up on everything — all day.
5. A missed WhatsApp message doesn't feel like a missed customer. It is one.

**Solution-led**
6. Meet the employee who answers, books, and follows up — before you've seen the message.
7. One AI employee. Every conversation, every booking, every lead, handled.
8. HIRA takes the front desk off your plate — for real, not in theory.
9. Your calendar, your leads, your customers — one employee keeping all three straight.
10. The job of answering WhatsApp all day now has someone doing it.

**Contrarian / category-defining**
11. Not a chatbot. An employee.
12. Software gets installed. HIRA gets hired.
13. Most AI tools answer questions. HIRA runs a job.
14. This isn't a bot you configure and hope works.
15. Stop managing a chatbot. Start managing an employee.

**Vision-led** *(use only where the vision is explicitly framed as direction, not current product)*
16. The first hire in a workforce that never sleeps.
17. Today, one employee. Eventually, a team that never clocks out.
18. Hire your first AI employee. It won't be your last.
19. Businesses used to hire people for this. Now they hire HIRA.
20. The Receptionist is the first role. It won't be the only one.

**Direct / confident**
21. Answers your customers from what you actually told it. Nothing invented.
22. Books the appointment. Updates the lead. Answers the question. One message.
23. It reviews with you until you trust it to act alone.
24. Every customer gets the right answer, the first time, instantly.
25. The front desk, covered — on WhatsApp, all day, every day.

**Question-led**
26. What's it costing you to answer WhatsApp an hour late?
27. How many leads went cold while you were with another customer?
28. What if the front desk never needed a lunch break?
29. Who's answering your WhatsApp at 9pm tonight?
30. What would you hire for, if hiring were this easy?

---

## 12. What HIRA IS

- An AI employee that takes over a real job: answering, booking, and following up.
- Grounded in a specific business's own knowledge — never inventing pricing, hours, or policy.
- One system: a single AI agent holds the conversation, the calendar, and the CRM together.
- Supervised by default: every action reviewable, editable, or overridable by a human until autonomy is earned.
- WhatsApp-native: it lives where the business's customers already are.
- Built to prove itself on one business before it's asked to prove itself on many.
- The first role in a direction, not the finished product of one.

## 13. What HIRA IS NOT

- A chatbot builder or a no-code flow you assemble yourself.
- A general-purpose assistant that tries to do everything for everyone.
- Autonomous by default — every business starts supervised, and stays there until it chooses otherwise.
- A wrapper around one vendor's API — the model, the embeddings, and the calendar are all swappable underneath.
- An "AI Business Operating System" yet — that's the direction, not the current product.
- A guess machine — if HIRA doesn't know, it says so and hands off; it doesn't improvise.
- Locked to one industry — built vertical-agnostic, proven so far on one real business.

---

## 14. Vocabulary Guide

| Say this | Not this | Why |
|---|---|---|
| AI employee | AI assistant, bot, virtual agent | The whole positioning depends on "employee." Never dilute it. |
| Hire (onboarding a business) | Sign up for, deploy, install | "Install" is correct only for the literal software (see README's own dev setup); never for how a business relates to HIRA. |
| The Receptionist (capitalized) | The receptionist feature, the chat module | It's a job title / proper noun, not a feature name. |
| Assisted Mode / Autonomous Mode | Auto mode, manual mode, review mode | Exact, capitalized product terms. |
| Grounded in your knowledge base | Trained on your data | HIRA retrieves from a knowledge base per message; it does not fine-tune or retrain a model per business. Say the real mechanism. |
| Escalate / hand off to a human | Fail, give up | Escalation is a designed outcome, not an error state. |
| Clinics, salons, gyms, consultants | SMBs, verticals | Internally "vertical" is fine; customer-facing copy names real business types. |
| Never invents an answer | Reduces hallucination | "Hallucination" is a technical term for an internal audience, not customer-facing copy. |

**Banned words** (generic AI-startup filler — replace with the actual mechanism): *leverage, utilize, seamless/seamlessly, empower, unlock, supercharge, revolutionize, game-changing, cutting-edge, next-generation, disrupt/disruptive, AI-powered (redundant — the category is already AI), smart (as a filler adjective), robust, holistic, solutions (as a vague noun), ecosystem, effortless, world-class, best-in-class, state-of-the-art, transform/transformative, journey (as in "customer journey").*

---

## 15. Copywriting Rules

1. One claim per sentence. If a sentence has two ideas, it's two sentences.
2. Every abstract noun needs a concrete mechanism in the same breath.
3. No feature gets a superlative it can't independently prove.
4. Never invent a metric, a customer, or a quote. If it wasn't measured, it didn't happen.
5. Prefer verbs a person actually does — *answers, books, escalates* — over nominalized abstractions — *engagement, automation, optimization*.
6. If a phrase can be cut without losing meaning, cut it.
7. Write it as if the founder has to say it out loud to a business owner who's never used AI software. If it would sound try-hard spoken aloud, rewrite it.
8. Every "not X" claim (like "not a chatbot") must be defensible in the very next sentence.
9. Don't explain a word the reader already knows. WhatsApp doesn't need an introduction.
10. When describing the vision (AI Business Operating System), always separate it from the current product in the same paragraph — never let the vision read like a shipped feature.

---

## 16. Homepage Messaging Hierarchy

The order a first-time visitor should meet the idea in, and the job each section does. Maps directly onto `frontend/src/components/marketing/*` (built Sprint 41) — several of those sections still say "AI receptionist" and need a copy pass against this document; see §20.

1. **Hero** — one sharp claim (a headline from the *contrarian* set in §11, e.g. "Not a chatbot. An employee.") plus one sentence of proof and a single CTA.
2. **Problem** — the real cost of a slow reply and a cold lead.
3. **Solution** — the single most differentiated claim HIRA has: one employee, not a bundle of bots. Currently under-emphasized on the live site relative to its importance.
4. **AI Employees** — reframed explicitly as the vision ladder (Receptionist live today; more roles ahead, direction not delivery date), not a generic section header.
5. **Features** — concrete capabilities, led by the least expected/most differentiated one (knowledge grounding, one-system unification) rather than the most obvious one (booking) first.
6. **How It Works** — unchanged in spirit; it's the real onboarding sequence.
7. **FAQ** — unchanged in spirit; add "Is this a chatbot?" as an explicit early entry given the repositioning.
8. **Final CTA** — restate the hire metaphor, not a generic "get started."

---

## 17. Product Naming Hierarchy

- **Company / platform**: **HIRA** — the employer, the platform, the brand.
- **Role name**: **the Receptionist** — a job title, not a feature name. Capitalize it as a proper noun once introduced, the way you'd capitalize a job title in running text ("the Receptionist," like "the CFO").
- **Mode names**: **Assisted Mode** / **Autonomous Mode** — properties of any role, not specific to the Receptionist. Every future role ships in Assisted Mode first, without exception.
- **Internal capabilities**: plain, descriptive, lowercase — *knowledge base, lead pipeline, calendar*. These are tools a role uses, not products in their own right. Don't over-brand internals.
- **Never**: "HIRA AI," "HIRA Bot," "HIRA Assistant," "HIRAbot" — redundant or actively diluting.

**Reference pattern**: "the Receptionist, hired by HIRA" or "HIRA's Receptionist" both read naturally on first mention. Once HIRA is already named in the same paragraph, prefer "the Receptionist" alone in running copy — the way you'd refer to an actual employee by title, not restate the company name every sentence.

---

## 18. Future AI Employee Naming Strategy

- Every new role gets a **real job title** — never a human first name. Explicitly reject the "meet Aria, your AI assistant" pattern: that convention is exactly the generic-AI-startup shorthand this brand is defined against, and it turns the employee metaphor cute instead of literal.
- Next roles already signaled on the marketing site's own roadmap badges: **Sales**, **Support**, **Scheduling**. Working names: *the Sales Rep*, *the Support Agent*. Whether Scheduling becomes its own hire or stays part of the Receptionist's existing calendar work is a naming decision to make at build time, against real need — not now, and not speculatively.
- Every role launches in Assisted Mode, no exceptions. State it plainly every time a role is introduced: never "meet the Support Agent — autonomous from day one."
- No role gets a personality distinct from HIRA's own voice. An employee has a job, not a separate mascot persona. The Receptionist and the Sales Rep should read like they work at the same company.
- Keep "AI Employees" (plural) strictly a vision-section phrase until more than one role actually exists in the codebase — mirror `README.md`'s own discipline on this exactly. Don't let marketing outrun engineering.

---

## 19. Competitor Positioning Map

Positioned by category, not by naming specific companies — the map below describes what's actually different about HIRA's *shape*, not a comparative attack on a competitor's claims we haven't independently verified.

**Axes**: Scope (answers messages only → runs the whole front desk) × Grounding (generic/scripted → grounded in this business's own knowledge).

| | Generic / scripted | Grounded in this business |
|---|---|---|
| **Answers messages only** | No-code WhatsApp chatbot builders — flow-chart bots, canned FAQ scripts, no calendar or CRM. | AI support/helpdesk point tools — answer from a knowledge base, stop at answering. No booking, no lead pipeline. |
| **Runs the whole front desk** | Booking/scheduling software with no real conversation — calendar-only widgets, generic online booking. Handles the calendar, not the customer. | **HIRA** — the only quadrant where one AI agent holds the conversation, the calendar, and the pipeline, grounded in what the business actually told it. |

The differentiated claim is the combination, not either axis alone: plenty of tools are grounded-but-narrow, and plenty are broad-but-generic. Nothing else in the category is both at once, held together as one employee.

---

## 20. Final Recommendation

Commit fully to **"AI employee, hired not installed"** as the spine of everything. Stop hedging with "AI receptionist" anywhere — including page titles and SEO metadata. "AI receptionist" describes a feature; "AI employee" describes the company.

Concrete next steps, in order:

1. **Rewrite the live marketing site's hero, solution, and features copy** (`frontend/src/components/marketing/*`, and the `metadata` export in `frontend/src/app/page.tsx`). The current hero headline — *"An AI receptionist that answers WhatsApp before your customer gives up"* — was correct for its sprint and is now the exact positioning this document retires. Not done in this pass; this document is the reference to write against, not the rewrite itself.
2. **Sync `.claude/PROJECT_CONTEXT.md`'s "What HIRA Is" section** — it still opens with "AI receptionist platform," which now contradicts `README.md`'s own already-updated positioning ("HIRA is an AI employee — not a chatbot"). Small, mechanical fix; flagged here rather than silently left stale.
3. **Hold the line on "AI Employees" (plural) and "AI Business Operating System"** — vision language only, every time, paired with the current-state disclaimer, exactly as `README.md` already does. The moment that discipline slips in a deck or a landing page, the brand starts making promises the codebase hasn't earned yet.
4. **Treat this document as load-bearing.** The same way the codebase checks itself against `.claude/CLAUDE.md`, every future landing page, deck slide, or feature announcement should be checked against this file before it ships. Logged as `DEC-036` in `.claude/DECISIONS.md`.
