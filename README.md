# HIRA

**HIRA is an AI Receptionist platform for WhatsApp-first businesses.**

It automatically responds to customer inquiries, answers FAQs from a business's own knowledge base, books and reschedules appointments, escalates complex conversations to a human, and makes sure businesses never miss a lead — all inside WhatsApp, where their customers already are.

## Vision

The long-term vision is an **AI Business Operating System**: a platform where small and medium businesses can "hire" AI employees to run different functions of the business — receptionist, sales follow-up, support, scheduling, and beyond.

HIRA starts narrow on purpose: the first goal is to become **the best AI Receptionist**, not to build the whole OS on day one.

## Current MVP

The MVP is deliberately small. It must:

- Reply to customers on WhatsApp
- Answer questions using a business's knowledge base
- Book appointments into Google Calendar
- Reschedule appointments
- Escalate uncertain conversations to a human
- Store conversation history
- Run in **Assisted Mode** first (human reviews/approves AI actions), with **Autonomous Mode** (AI acts independently) coming later once trust is established

No feature ships before customer validation justifies it.

## Goals

- Validate product-market fit with one primary vertical before expanding to others.
- Keep the system small, reliable, and trustworthy — a missed message or a wrong booking costs a business real customers.
- Build the AI engine and prompts as first-class, version-controlled artifacts, not afterthoughts bolted onto backend code.
- Grow from "AI Receptionist" toward "AI Business Operating System" only after the receptionist product proves itself.

### Customer segments under evaluation

Currently researching, to select **one** primary vertical for the first production version, based on market demand, willingness to pay, ease of sales, and product-market fit:

- Dental Clinics
- Beauty Salons
- Immigration & Study Abroad Consultants
- Gyms & Fitness Centers
- Real Estate Agencies & Property Consultants
- Cafés & Restaurants

## Repository Structure

| Folder | Purpose |
|---|---|
| [`documentation/`](documentation/README.md) | Architecture, onboarding, and domain knowledge that isn't code |
| [`backend/`](backend/README.md) | Server-side application: webhooks, business logic, integrations |
| [`frontend/`](frontend/README.md) | Business owner dashboard and admin tooling |
| [`infrastructure/`](infrastructure/README.md) | Hosting, environments, CI/CD, infra-as-code |
| [`ai/`](ai/README.md) | The AI engine: conversation orchestration, tools, retrieval, evaluation |
| [`prompts/`](prompts/README.md) | Version-controlled system prompts and templates |
| [`database/`](database/README.md) | Schema, migrations, seed data |
| [`testing/`](testing/README.md) | Automated tests and AI conversation evaluation sets |
| [`deployment/`](deployment/README.md) | Release procedures, runbooks, rollback plans |
| [`roadmap/`](roadmap/README.md) | Feature/vertical sequencing from MVP to the larger vision |
| [`business/`](business/README.md) | Market research, pricing, go-to-market |
| [`learning/`](learning/README.md) | Lessons learned along the way — technical and startup |
| [`progress/`](progress/README.md) | Dated factual log of what's actually been built |
| [`portfolio/`](portfolio/README.md) | External-facing material: pitch decks, demos, case studies |
| [`.claude/`](.claude/CLAUDE.md) | Claude's operating manual and project memory for this repo |

Each folder contains its own `README.md` explaining its purpose in more detail.

## Technology Philosophy

- **Boring and reliable over clever.** HIRA acts on behalf of real businesses with real customers — a missed WhatsApp reply or a double-booked appointment has real cost. Well-understood, proven technology is preferred over novelty.
- **Small surface area until validated.** No feature, abstraction, or infrastructure investment ships ahead of a proven need. See [CLAUDE.md](.claude/CLAUDE.md) Section 14.
- **AI as a first-class, reviewable system.** Prompts and tool definitions are version-controlled and inspectable, not hidden in code. AI failure modes (hallucination, uncertainty) are designed for explicitly — escalation to a human is a core feature, not a fallback.
- **Assisted before Autonomous.** Trust is earned incrementally. The system gives a human the final say before it's given full autonomy.

Full engineering standards, coding conventions, and decision-making framework live in [CLAUDE.md](.claude/CLAUDE.md).

## Roadmap Summary

1. **Validate**: Research and narrow the six candidate verticals down to one primary target.
2. **MVP**: Ship Assisted Mode AI Receptionist (WhatsApp + knowledge base + Google Calendar booking/rescheduling + escalation) for the chosen vertical.
3. **Pilot**: Onboard early customers in that vertical, measure real usage and feedback.
4. **Autonomous Mode**: Once trust and accuracy are proven, allow the AI to act without per-action human approval.
5. **Expand**: Bring the validated receptionist product to adjacent verticals.
6. **AI Business OS**: Introduce additional AI "employee" roles beyond receptionist.

Detailed planning lives in [`roadmap/`](roadmap/README.md).

## Contribution Guidelines

This is currently a solo-founder project built in close collaboration with Claude acting as technical cofounder (see [CLAUDE.md](.claude/CLAUDE.md)). Until external contributors are involved:

- All standards in [CLAUDE.md](.claude/CLAUDE.md) apply to any code or documentation added to this repo.
- No application code ships without the founder's explicit approval of scope first.
- Documentation is updated in the same change that makes it necessary, not deferred.

This section will be expanded with real contribution guidelines if/when the project takes on other contributors.

## Development Workflow

1. Define scope for the change (feature, fix, research) before writing code.
2. Read relevant docs in `.claude/` and the affected folder's `README.md` for context.
3. Build the smallest working version of the change.
4. Verify it actually works (run it, don't just inspect it) before calling it done.
5. Update any documentation the change affects.
6. Get explicit approval before committing, pushing, or deploying.

Full workflow and definition of done live in [CLAUDE.md](.claude/CLAUDE.md) Sections 15–17.
