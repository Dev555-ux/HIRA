# Founder Beta Tracker

The master dashboard for HIRA's first Founder Beta. Everything else in `beta/` feeds this file: bug reports and feature requests roll up into Top Issues, `AI_FAILURE_LOG.md` rolls up into AI Failures, `TRACKING_BOARD.md` rolls up into the tester/session counts. Update this weekly at minimum — a stale dashboard is worse than no dashboard, because it creates false confidence.

---

## Beta Overview

| Field | Value |
|---|---|
| Start Date | |
| End Date | |
| Current Version | |
| Knowledge Base Version | |
| Number of Testers | |
| Number of Sessions | |
| Number of Bugs | |
| Number of Feature Requests | |
| Number of AI Failures | |
| Overall Beta Status | Not Started / In Progress / Wrapping Up / Complete |

**Knowledge Base Version** matters specifically because AI failures need to be traceable to *what HIRA knew at the time* — if you edit a tester's Business Knowledge mid-beta (or ship a fix to `beta/DEMO_BUSINESS_KNOWLEDGE_VELOCITY_LUXE_MOTORS.md`), log the version bump here so a failure logged on day 3 can be re-checked against day 10's knowledge without ambiguity about whether it's actually fixed.

**Overall Beta Status** is a single word, not a paragraph — the detail lives in the sections below. Move it forward deliberately, not automatically on a calendar date; "In Progress" should mean testers are still actively generating new signal, not just that the end date hasn't arrived yet.

---

## Beta Goals

What this beta needs to answer before Sprint 62 gets planned — not a wishlist, a validation list:

- **Validate onboarding** — can a real business owner get from signup to a working, knowledge-grounded HIRA without help?
- **Validate Business Knowledge** — does uploaded content actually ground HIRA's answers, or does it fall back to guessing?
- **Validate Demo Chat / Playground** — is this a convincing enough preview that testers trust the real (WhatsApp) experience will match it?
- **Validate CRM** — do leads get created, updated, and found the way a real sales process needs?
- **Validate Calendar** — do booking, rescheduling, and cancellation actually work end-to-end, including the confirmation/readiness behavior HIRA is supposed to apply before acting?
- **Measure user understanding** — do testers know what HIRA can and can't do without being told, or is the product explaining itself poorly?
- **Measure AI accuracy** — when HIRA answers a real question, is the answer actually correct, not just fluent?

Each goal above should be answerable from evidence already sitting in this folder by the time the beta ends — not from a founder's gut feeling. If a goal can't be answered from the data collected, that's itself a finding: the tracking wasn't capturing the right thing, and the next beta's instrumentation should change accordingly.

---

## Current Metrics

| Metric | Target | Current |
|---|---|---|
| Onboarding Success | 90% | |
| AI Accuracy | 95% | |
| Knowledge Accuracy | 95% | |
| Session Completion | 80% | |
| Critical Bugs | 0 | |

**AI Accuracy vs. Knowledge Accuracy are deliberately separate rows.** AI Accuracy is "did HIRA answer correctly, period." Knowledge Accuracy is narrower — "when the answer depended on uploaded Business Knowledge, did HIRA retrieve and use it correctly." A tester can have a bad AI Accuracy week for reasons that have nothing to do with their knowledge base (a hallucinated capability claim, a wrong intent classification) — collapsing these into one number hides which system to actually go fix. See `AI_FAILURE_LOG.md`'s Issue Type column for the same distinction applied per-incident.

**Critical Bugs** should read 0 for most of the beta, by definition — see `PRIORITIZATION_FRAMEWORK.md`'s Critical Bug category, which is meant to get same-day fixes. A non-zero number sitting here for more than a day is the single strongest signal in this entire dashboard that something needs the founder's attention right now.

---

## Daily Beta Log

| Date | Tester | Duration | Major Findings | Follow-up Required |
|---|---|---|---|---|
| | | | | |

Log an entry per tester session, not per day — if three testers use HIRA on the same day, that's three rows. "Major Findings" is for the one or two things that actually mattered from that session (a bug hit, a real "aha" moment, an AI failure) — not a transcript. If nothing notable happened, write "nothing notable" rather than leaving the row blank; a blank row is indistinguishable from "forgot to log it."

---

## Top Issues

| Priority | Description | Owner | Status |
|---|---|---|---|
| | | | |

Priority values come from `PRIORITIZATION_FRAMEWORK.md` (Critical Bug / High Priority / Medium Priority / Nice to Have / Ignore), not an ad-hoc scale — using the same five labels here as in the bug and feature-request templates is what makes this table an actual roll-up rather than a second, disconnected list. Owner is a name, not a team — with a founder-run beta there's rarely ambiguity about who's fixing what, but writing it down still forces the decision to happen at triage time instead of being assumed later. Sort this table by Priority before every weekly review; Critical and High items belong at the top, not wherever they happened to be added.

---

## Sprint Recommendations

*(Leave blank during the beta — fill this in only once `POST_BETA_SUMMARY.md` has been completed. Recommendations written mid-beta, before the evidence is in, tend to lock in whatever the founder already believed going in.)*
