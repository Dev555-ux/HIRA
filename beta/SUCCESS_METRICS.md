# Beta Success Metrics

Two kinds of metrics matter here, and they get confused easily: **activation** (did they experience the product at all) and **value** (did they get anything out of it). A beta can hit 100% activation and still fail on value — that's the actual failure mode to watch for with 5–10 users, since it's easy to declare victory on "everyone signed up."

## Activation funnel (did they get through the door)

Track each of these as a simple yes/no per user — this is what `TRACKING_BOARD.md` records.

| Step | Metric | Target (5–10 users) |
|---|---|---|
| Signup | Completed account creation | 10/10 |
| Onboarding | Completed the onboarding flow (business created) | 9/10 — one drop-off here is a red flag worth a direct message, not a shrug |
| First knowledge | Uploaded at least one Business Knowledge fact/document | 8/10 |
| First AI interaction | Sent ≥5 messages in Demo Chat | 7/10 |
| First CRM action | Created at least one lead | 5/10 — lower bar; not everyone's workflow needs this on day one |
| Return visit | Came back and used HIRA again within 24 hours of first session | 5/10 |
| Return visit (week) | Used HIRA on ≥3 separate days in the first week | 4/10 |

If activation numbers are *below* these targets, the problem is almost certainly onboarding friction or a bug, not "the product isn't valuable" — check `TESTER_CHECKLIST.md` completion and bug reports before concluding anything about product-market fit.

## Value signals (did it actually help)

These are qualitative-but-trackable — record them as short notes on the tracking board, not just yes/no:

- **At least one "aha" moment reported.** A tester says some version of "oh, it actually got that right" or "that would've saved me a phone call." Capture the literal quote — it's your best raw material for later positioning.
- **At least one real (non-test) question asked in Demo Chat.** Distinguishes "I was told to try this" from "I had an actual question and used the tool for it."
- **Unprompted return usage.** They came back without you nudging them. This is the strongest single signal you have — a feature-complete demo that nobody voluntarily reopens is a real warning sign regardless of how the checklist scored.
- **At least one piece of critical feedback with specifics.** ("The AI didn't know our return policy" is useful; "it's fine" is not.) If every tester says "looks good," you don't have signal — you have politeness. Push for specifics in `FEEDBACK_FORM.md`.

## The one number that matters most

**How many of the 5–10 testers would be upset if HIRA disappeared tomorrow?** (This is the literal Sean Ellis / "40% test" question, and it's in the feedback form for exactly this reason.) For a 5–10 person beta, even 2–3 genuine "very disappointed" answers is a meaningfully strong signal — don't need a majority to have real evidence of value, but you do need it to be more than one person.

## What "the beta worked" means, concretely

Not "we ran a beta and nothing crashed." It means: **you can name, with specifics, at least 2–3 real workflows HIRA clearly helped with, and at least 2–3 concrete things that need to change before the next cohort** — sourced from evidence in this folder, not from your own assumptions going in.
