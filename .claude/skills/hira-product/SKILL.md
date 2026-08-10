---
name: hira-product
description: HIRA's permanent product philosophy — what belongs in the product, what doesn't, and how to judge any proposed feature or capability. Use before proposing, scoping, or evaluating any HIRA feature, capability, notification, or new interaction surface — not for visual design or implementation.
---

# HIRA Product Philosophy

This skill teaches product judgment, not design or code. It decides what
HIRA should become — which features earn a place in the product, which
capabilities stay features rather than becoming products of their own, and
which "good ideas" get rejected because they add software without reducing
work. If you're deciding *whether* to build something, or *what* it should
do, this is the skill that governs. If you're deciding *how something
should look*, that's `hira-design`. If you're deciding *how to design any
interface well in general*, that's `frontend-design`.

## How the three skills divide the work

- **`frontend-design`** (Anthropic's general craft skill): how to design any
  interface distinctively — typography, layout, motion, avoiding generic
  AI-design defaults. Subject-agnostic.
- **`hira-design`**: HIRA's visual and interaction identity — warm tokens,
  narrative-over-dashboard layout, Ask HIRA's presentation. Governs *how
  HIRA-the-product should feel* once a feature already exists.
- **`hira-product`** (this skill): whether a feature should exist at all,
  and what it should actually do. Governs *before* the other two are
  relevant — a feature that fails this skill's tests shouldn't reach a
  design pass in the first place.

**Precedence**: `hira-product` runs first, on scope. If a proposed feature
fails the workload test or the success test below, reject or reshape it
before any visual work starts — a well-designed dashboard nobody needed is
still a wasted build. Once a feature has been product-approved, `hira-design`
and `frontend-design` govern how it's presented, and neither of those two
skills gets to smuggle a rejected feature back in via "but it would look
good." Scope and craft are separate votes; scope votes first.

## What HIRA is

HIRA is an AI Business Operating System. A small business owner hires HIRA
the way they'd hire a competent employee — to actually do the work of
running parts of the business, not to give them a better view of it.

HIRA is **not** any of the following, even though it may contain pieces
that look like them:

- A CRM — a system a human uses to record and track work.
- A chatbot — a system that answers when spoken to and otherwise sits idle.
- A workflow builder — a system the user configures with logic they design.
- An analytics dashboard — a system that surfaces numbers for a human to
  interpret.
- A ticketing platform — a system that queues unresolved problems for a
  human to work through.

Each of these is a **capability** HIRA may use internally (HIRA does track
customer state, does respond to messages, does follow rules, does surface
numbers, does hold open items) — but none of them is what HIRA *is*. The
product is the outcome — work done on the owner's behalf — not the
mechanism that produces it. A feature can borrow the mechanics of a CRM or
a dashboard without HIRA becoming one, as long as the mechanics stay in
service of action rather than becoming the point.

## Core philosophy

Every feature must answer one question honestly:

> **Does this reduce the business owner's workload?**

Not "is this useful," not "would this be nice to have," not "do competitors
have this." Workload reduction specifically — time, decisions, or attention
the owner no longer has to spend. If a feature's honest answer is no, or
"it gives the owner more to look at," it probably doesn't belong, no matter
how well-executed it would be.

This is a filter applied at proposal time, not a retrospective excuse. When
a feature idea shows up, ask this before scoping it, not after building it.

## AI philosophy: notice, decide, act

HIRA is proactive, not reactive. The default posture for any new capability
should follow this sequence:

1. **HIRA notices** — it detects a situation from data it already has,
   without being asked to look.
2. **HIRA decides** — it determines what should happen, using its own
   judgment and confidence, not by handing a raw decision to the owner.
3. **HIRA acts** — it does the thing, when it's safe to do so.
4. **The owner is informed** — after the fact, as part of the ongoing
   narrative (see `hira-design`'s Home philosophy), not as a request for
   permission to have acted.

A feature that only completes step 1 (notices, then stops) is a
notification system, not an AI employee doing its job — treat "we detected
X" as an incomplete feature, not a finished one, unless one of the
interruption conditions below applies.

**Only interrupt the owner when:**

- Approval is genuinely required (the action can't be undone or delegated).
- Confidence is low enough that acting without a human would be a guess.
- Money is at risk.
- Reputation is at risk (a customer-facing action that could go wrong publicly).
- Legal or compliance obligations require a human in the loop.

Outside of those five conditions, default to acting and reporting, not
asking and waiting. Every time a feature proposal adds a confirmation step,
name which of the five conditions justifies it — if none apply, remove the
step.

## Decision framework

For any feature under consideration, ask:

> "Does this make HIRA feel more like an **employee**, or more like
> **software**?"

An employee notices things, uses judgment, does the work, and tells you
what happened. Software waits for input, requires configuration, and shows
you data. If the honest answer is "software," rethink the feature before
building it — not by making the software prettier, but by finding the
version of the idea where HIRA is the one doing the work.

This framework applies at every scale: a single button, a whole page, or an
entire new capability area. A feature can fail this test even if it's
technically impressive — impressiveness is not the test.

## Feature principles

**Prefer:**

- Automation — HIRA doing the recurring thing, not a human repeating it.
- Memory — HIRA remembering context so the owner never has to re-explain it.
- Context — surfacing the "why," not just the "what."
- Recommendations — a specific next step, not a raw signal.
- Work completed — evidence of action taken, framed as done, not pending.
- Summaries — the meaning of a period of activity, not its raw feed.
- Decisions — the few things that genuinely need the owner's judgment.

**Avoid:**

- Manual workflows — anything that makes the owner the one operating the process.
- Forms — data entry is work moving from HIRA to the human, backwards.
- Configuration screens — settings the owner must maintain are a standing
  workload cost, not a one-time convenience.
- Empty dashboards — a screen that exists to be checked rather than to say
  something.
- Feature bloat — capabilities added because they're easy to build or look
  complete, not because a real workload need named them.

## Home screen

The Home screen exists to answer four questions, and no others need to be
invented for it:

- What happened?
- What needs me?
- What is HIRA doing?
- What should I do next?

Any proposed Home content should be traceable to one of these four. If it
isn't, it belongs on a different screen or not in the product at all — see
`hira-design` for how these four questions are actually laid out.

## Ask HIRA

Ask HIRA is the primary interaction model for the entire product, not one
feature among several. As new capabilities are proposed, the default
expectation is that they become reachable through Ask HIRA eventually, even
if they also get a dedicated surface for other reasons (e.g. a calendar
view for browsing appointments visually).

Do not create a new parallel interaction model (a separate assistant, a
second chat surface, a distinct "ask" pattern scoped to one feature) without
a strong, explicit reason tied to a real constraint — not convenience during
implementation. Two ways to ask HIRA for something is a product split, not a
feature.

## Product rules

These are non-negotiable regardless of how compelling a specific feature
pitch is:

- Never invent metrics. A number on screen must trace to a real, existing
  data source — see `ARCHITECTURE.md` / `PROJECT_CONTEXT.md` for what
  currently exists.
- Never fabricate AI recommendations. If there's no real signal to base a
  recommendation on yet, the honest move is to not show one, not to
  simulate one.
- Never create fake notifications to make the product feel more active
  than it is. Perceived proactivity built on fabricated events is a
  liability, not a feature — it breaks trust the moment it's noticed.
- Never build a dashboard, chart, or panel because a competitor has one.
  Competitive parity is not a workload-reduction argument.
- Always reuse existing backend capabilities before proposing a new API,
  model, or data source. Check what's already built (`ARCHITECTURE.md`)
  before assuming a feature needs new infrastructure — most feature ideas
  are a new arrangement of existing signals, not a new signal.

## Success test

Before finalizing any feature proposal, ask:

> "If this feature disappeared tomorrow, would the owner need to do more
> work?"

If the honest answer is no — the owner's workload is unchanged either way —
the feature isn't earning its place, regardless of how polished or
technically interesting it is. A feature only justifies itself by being
something the owner would miss doing without.

This is the same filter as the core philosophy question, asked in reverse,
at the end of scoping rather than the start. Use both: if a feature passes
one but fails the other, that's a signal the feature has been reshaped into
something different from what it started as — check which version is
actually being proposed before it ships.
