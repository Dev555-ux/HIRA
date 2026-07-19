# AI Failure Log

This is the most important document in the beta folder. Bugs tell you the product broke; this tells you the *AI* was wrong while the product worked perfectly — a categorically different (and harder to notice) failure mode, since a wrong-but-fluent answer doesn't crash anything and a tester may not even flag it as a problem.

One row per failed exchange. Log it the moment you notice it, or the moment a tester reports it — don't wait to batch these, the exact wording of the question and answer matters and is easy to lose after the fact.

---

## Log

| Date | Question Asked | Expected Answer | Actual Answer | Issue Type | Root Cause | Fix Required | Resolved Version |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

**Question Asked** — the exact text sent to HIRA, verbatim. Not a paraphrase — "asked about pricing" is useless for reproduction; "What's the price of the Range Rover?" is reproducible.

**Expected Answer** — what a correct answer would have contained, not necessarily word-for-word. If the honest expected answer is "I don't know, ask a human," write that — a failure isn't always about a wrong fact, sometimes it's HIRA confidently answering something it should have declined to.

**Actual Answer** — verbatim, or as close as you can capture it. Paste it, don't summarize it; the exact phrasing is often the diagnostic clue (e.g. hedging language that reveals the model was guessing).

**Resolved Version** — which build/Knowledge Base version actually fixed it, filled in after the fact. A row with everything filled in except this one means "confirmed broken, not yet fixed" — that's a valid, expected state mid-beta, not a gap in the log.

---

## Issue Type — pick exactly one, and use this table to route it

HIRA's reply pipeline has distinct stages (Context → Knowledge Retrieval → Intent Classification → Tool Selection → Action Planning → Execution Governance → Response), and each Issue Type below maps to a specific stage. Picking the right one tells whoever triages this exactly where to look — this is the whole reason the log exists, not just a record of "AI got it wrong."

| Issue Type | What it looks like | Points to |
|---|---|---|
| **Hallucination** | HIRA stated a specific fact (a price, a policy, a name) that isn't in the Business Knowledge and isn't true | The prompt/grounding, or a gap in the uploaded Business Knowledge that invited a guess |
| **Missing Knowledge** | HIRA correctly said it didn't know, or answered vaguely, because the fact genuinely isn't in the Business Knowledge yet | Not a bug — a knowledge gap. Goes back to whoever owns the Business Knowledge document, not to the AI pipeline |
| **Retrieval Failure** | The fact *was* in the Business Knowledge, but HIRA didn't find/use it — answered generically or wrongly despite the document having the answer | Knowledge retrieval (embedding/search), not the LLM's reasoning |
| **Wrong Intent** | HIRA treated a real action request as a conversational question (or vice versa) — e.g. "cancel tomorrow's appointment" got a chatty non-answer instead of engaging the cancellation flow | Stage 1 classification (conversation / capability / knowledge / action) |
| **Wrong Planning** | HIRA correctly recognized an action request but proceeded despite missing required details, or asked for a detail it already had | Action readiness checking — the step that should hold back tools and ask a clarifying question before an incomplete request goes further |
| **Wrong Tool** | HIRA correctly recognized an action but reached for the wrong category — e.g. treated a CRM request as a calendar request | Tool selection/routing once an action's category is chosen |
| **UX Confusion** | The AI's answer was technically correct but confusing, oddly worded, or left the tester unsure what to do next | Not a factual error — a phrasing/experience problem. Often means the right information was returned in the wrong shape |

A borderline case worth calling out specifically: HIRA proceeding straight to an action it should have confirmed first (e.g. treating a cancellation as done without checking) is **not** Wrong Planning — planning is about whether enough *information* exists to act. This is about whether the action was *allowed* to proceed automatically at all. Log that as **Wrong Tool** if the wrong action executed, or as a bug (not an AI failure) if the confirmation step should have run and simply didn't. If you're not sure which, log it here anyway with your best guess — a mislabeled entry that gets corrected in triage is still more useful than a failure that never got logged because the category wasn't obvious.

---

## Weekly review

Before every `FOUNDER_BETA_TRACKER.md` update, scan this log for the same Issue Type or the same underlying fact recurring across different testers or different phrasings — one Hallucination is a data point, three separate testers hitting the same wrong fact is a pattern that belongs in Top Issues at High or Critical priority, not sitting quietly in this table. See `PRIORITIZATION_FRAMEWORK.md`'s note on convergence across testers mattering more than any single loud report.
