# Bug Report Template

Copy this block for every bug — from you, from a tester, or from a log you noticed yourself. One bug per report; don't bundle two unrelated issues into one ticket, it makes prioritization and status tracking ambiguous.

```
Date:
  When it happened, not when you're writing this up if the two differ.

Tester:
  Who hit it. Needed to follow up ("did the fix actually resolve it for you?")
  without re-reading the whole conversation to figure out who reported it.

Feature:
  Which area: Onboarding / Business Knowledge / Demo Chat / CRM / Calendar /
  WhatsApp / Dashboard / Other. This is what makes "Most Common Bugs" in
  POST_BETA_SUMMARY.md answerable — without it, every pattern-spotting pass
  means re-reading every title again.

Title:
  One line, specific enough to identify at a glance.
  Bad:  "Demo Chat broken"
  Good: "Demo Chat shows a network error when asking about booking availability"

Severity:
  Critical  — blocks the core workflow, no workaround, affects most/all users
  Major     — blocks a real workflow, but a workaround exists, or affects some users
  Minor     — cosmetic, or a real but low-impact issue
  (Severity is about impact. Priority, below, is about what to do about it — they're
  not the same axis; see PRIORITIZATION_FRAMEWORK.md.)

Steps to reproduce:
  1.
  2.
  3.
  (Be literal. "I asked about pricing" beats "I used the chat feature.")

Expected behaviour:
  What should have happened.

Actual behaviour:
  What actually happened. Paste the exact error text if there was one —
  don't paraphrase it.

Browser:
  (Chrome/Safari/Firefox + version, if known)

Device:
  (Desktop/mobile, OS)

Screenshot:
  (Attach if at all possible — a screenshot resolves more ambiguity than a
  paragraph of description)

Priority:
  Critical Bug / High Priority / Medium Priority / Nice to Have / Ignore —
  see PRIORITIZATION_FRAMEWORK.md for what each means and who assigns it
  (hint: not the reporter — you, after triage)

Status:
  New → Confirmed → In Progress → Fixed → Verified → Closed
  (or: New → Confirmed → Won't Fix → Closed, if that's the call)
```

## Notes for triaging what testers send you

Beta testers will rarely fill this out completely — most will send "the chat thing didn't work" over text or email. That's fine. Your job in triage is to convert their report into this format yourself, filling gaps by asking one clarifying question ("what did you actually type?") rather than guessing. A bug report you can't reproduce from is not yet a bug report — it's a lead on one.
