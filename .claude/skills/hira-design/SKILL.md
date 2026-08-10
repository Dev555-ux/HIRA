---
name: hira-design
description: HIRA's permanent product design philosophy — what HIRA is, why its UI must never read as a CRM or dashboard, and the decision framework for judging any HIRA frontend change. Use for any design or UI work on HIRA's frontend, including Home, Ask HIRA, and every authenticated app screen.
---

# HIRA Design Philosophy

This is a philosophy, not a style guide. It doesn't specify hex values or
component APIs — those live in the codebase (`frontend/src/app/globals.css`
for tokens, `frontend/src/components/` for primitives). This skill exists so
that every design decision on HIRA, made in any session, answers to the same
identity instead of drifting toward generic SaaS defaults one page at a time.

Pair this with `frontend-design` (Anthropic's general craft skill) rather
than instead of it. `frontend-design` teaches how to make any interface
distinctive — hero-as-thesis, deliberate typography, avoiding templated
AI-design defaults, writing copy that helps rather than decorates. This
skill tells you what HIRA specifically is, so that craft gets pointed the
right direction. Read `frontend-design` for *how* to design well; read this
for *what HIRA is designing toward*. When they conflict on a HIRA-specific
call — e.g. frontend-design suggesting a data-viz-heavy hero — this skill
wins, because the brief's own identity always overrides a generic default.

## What HIRA is

HIRA is an AI Business Operating System. A small business owner delegates
real work to it — replying to customers, tracking jobs, following up,
scheduling — and HIRA does that work, not just records it.

HIRA is **not**:

- A CRM. CRMs are systems of record — you go to them to log what already
  happened. HIRA is a system of action — it tells you what it already did.
- An analytics dashboard. Dashboards report numbers back to a human who
  must interpret them. HIRA interprets first and hands over a conclusion.
- A ticketing system. Tickets are units of unresolved work waiting on a
  human. HIRA's default state is resolving things before they become tickets.
- A chatbot. A chatbot answers when spoken to. HIRA acts without being
  asked and reports on that action.
- A workflow builder. Workflow builders make the user configure the logic.
  HIRA already knows the logic; the user supervises and corrects it.

Every UI decision either reinforces "AI employee already at work" or it
erodes it toward one of the five things above. There is no neutral choice —
a chart, a card grid, or a settings-style form all quietly vote for "CRM"
unless something in the design actively votes against it.

## Home is not a dashboard

Home is the workspace of an AI Chief Operating Officer, not a summary
screen. A dashboard's job is to be scanned; Home's job is to be read, the
way you'd read a brief from a competent operator who worked the business
overnight. Landing on Home should answer, in order:

1. **What happened?** — what HIRA did while the owner wasn't watching.
2. **What needs me?** — the small number of things only a human can decide.
3. **What is HIRA doing right now?** — proof of ongoing work, not a status log.
4. **What should I do next?** — a recommendation, not a raw metric to interpret.

The existing Home narrative (Morning Brief, Ask HIRA, Needs Your Attention,
Business Health, Today's Activity, AI Recommendations, Revenue & Pipeline,
Learned Today — see `dashboard-hero.tsx` and the dashboard page) is the
reference shape for this. Extend that narrative; don't fall back to a card
grid because a new data point needs a home. If a new signal doesn't fit
one of the four questions above, it probably doesn't belong on Home at all.

## Ask HIRA is the center, not a feature

Ask HIRA (`ask-hira-bar.tsx`) is the primary interaction surface, not a
support widget bolted onto a dashboard. It should never be styled, sized,
or positioned like "one more card" competing with the rest of the page for
attention. If a redesign would make Ask HIRA feel optional or skippable,
that redesign is wrong regardless of how good it looks otherwise. When in
doubt about where a new capability should live, "make it reachable from
Ask HIRA" beats "give it its own settings page."

## The interface must feel proactive

Reactive UI waits for input and then responds. Proactive UI shows its own
initiative: things already done, things already noticed, things already
queued, before the user asks. Prefer past-tense and present-continuous
framing ("Replied to 3 customers," "Watching for late invoices") over
imperative prompts that put the burden of starting work back on the user.
Loading and empty states are part of this: an empty state on HIRA should
read as "nothing needs you right now" (a good outcome), never as "no data"
(a system waiting to be fed).

## Information hierarchy

Prefer, in this order:

- A narrative sentence over a KPI wall.
- A written summary over a dashboard panel.
- A decision to make over a statistic to notice.

A number is only worth showing if it changes what the owner does next. If a
metric would just sit there being observed, it's decoration wearing the
costume of insight — cut it or fold it into the sentence that explains why
it matters.

## Visual language (HIRA V2)

The current token layer is the source of truth
(`frontend/src/app/globals.css`); this is the intent behind it, not a
duplicate spec:

- Warm, not cool. Neutrals are warm ink, not blue-grey; the accent is a
  coral-vermilion "Signal," not corporate blue. Warmth reads as an operator
  in the room, not a server render.
- Generous whitespace and a confident type scale over density. Type carries
  hierarchy; borders shouldn't have to.
- Calm motion — orchestrated, not scattered. Motion should feel like
  something is being handled, not like the UI is performing for the user.
- Elevation over borders. Cards are shadow-defined (`e2-resting`), not
  boxed in hairlines. A hard 1px border reads as "form," which reads as CRM.
- Rounded, soft geometry (16px radius) over sharp corporate-SaaS rectangles.

Avoid by default: chart-first layouts, dense card grids, heavy borders,
generic three-column-feature-tile marketing patterns, and any layout that
would look identical if you swapped in a different company's logo.

## UX principles

Every screen, not just Home, should be answerable from these three
questions. If a screen can't answer at least one, question whether the
screen needs to exist in its current form:

- **What happened?** — context, not raw logs.
- **What matters?** — signal, filtered from noise, not every field available.
- **What should I do?** — a next step, even if the step is "nothing, HIRA has it."

## Decision framework

Before shipping any HIRA UI decision, ask:

> "Does this make HIRA feel more like an AI employee, or more like a CRM?"

If the honest answer is CRM — even a well-designed one — reject the design
and find the version that answers "AI employee" instead. This framework
outranks visual polish: a beautiful CRM screen is still the wrong screen.

## Non-negotiables

- Never fabricate data, metrics, or activity that didn't happen. If a
  section (e.g. Revenue & Pipeline, AI Recommendations) has no real backend
  signal to show yet, say so honestly in the UI or leave it unbuilt — don't
  simulate one to fill a layout.
- Never invent a KPI because "dashboards usually have one." Every number on
  screen must trace back to a real, existing data source.
- Never add a chart because the layout looks empty without one. A missing
  chart is not a bug; an unjustified chart is.
- Never add a widget, card, or panel without a real user decision or action
  it serves. If you can't name the decision it enables, cut it.
- Reuse existing backend logic and APIs as-is. This skill governs
  presentation and interaction design, not data models, endpoints, or
  business logic — those are out of scope for a design pass.
- Redesign the experience, not the system underneath it. If a design idea
  requires a new endpoint or a schema change, that's a product conversation
  to have explicitly, not something to assume mid-redesign.
