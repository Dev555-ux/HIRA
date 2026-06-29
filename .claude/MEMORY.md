# MEMORY.md

Permanent, cross-session memory for the HIRA project. Only long-term information lives here — facts, principles, and lessons that should still be true and relevant many sessions from now. Temporary tasks, in-progress work, and short-lived notes belong in `TODOS.md` or `PROGRESS.md`, never here.

Update this file whenever something important and lasting is learned. If new information conflicts with an existing entry, update that entry in place — do not duplicate it. Never invent information; mark anything not yet confirmed as **Pending Validation**.

## Project Identity

- **Name**: HIRA
- **What it is**: An AI Receptionist platform for WhatsApp-first businesses. Automatically responds to customer inquiries, answers FAQs from a business's knowledge base, books and reschedules appointments, escalates complex conversations to a human, and aims to ensure businesses never miss a lead.
- **Founder/operating model**: Solo founder, building with Claude acting as technical cofounder.

## Founder Profile

- **Background**: B.Com (Hons.) student, **beginner-level programmer**, learning software engineering while building HIRA.
- **Goals**: (1) build a real SaaS business; (2) learn professional software engineering deeply; (3) build a strong GitHub portfolio; (4) offer AI automation services on Fiverr; (5) **understand every technology rather than copy code**.
- **Resources**: has time to learn; **no large budget; no development team**.
- **How Claude should optimize every technical decision**: for **learning, simplicity, maintainability, and production readiness**. When multiple options exist, recommend the one that **maximizes long-term learning while still allowing a fast MVP ship**.
- **Teaching implication**: explain the *why* and the fundamentals, not just the answer; never hand over copy-paste code without ensuring understanding (reinforces CLAUDE.md §8 Teaching Philosophy). Capture concepts learned in the `learning/` folder.

## Vision

- Long-term: an **AI Business Operating System** — a platform where businesses "hire" AI employees across different business functions.
- Near-term: deliberately narrow. The goal is to become the best AI Receptionist before expanding to any other function or role.

## Product Principles

- The MVP stays as small as possible; no feature ships ahead of customer validation.
- **Assisted Mode** (human reviews/approves AI actions) ships before **Autonomous Mode** (AI acts independently) — trust is earned incrementally.
- Escalation to a human is a core feature, not a fallback — uncertainty should be handled by handing off, not guessing.

## Business Principles

- Pick one primary vertical after validation, rather than building for all customer segments at once.
- Vertical selection criteria: market demand, willingness to pay, ease of sales, and product-market fit.
- Pricing model: **Pending Validation**.

## Target Customers

Six verticals currently under evaluation for the first production version:
- Dental Clinics
- Beauty Salons
- Immigration & Study Abroad Consultants
- Gyms & Fitness Centers
- Real Estate Agencies & Property Consultants
- Cafés & Restaurants

Which one becomes the primary target: **Pending Validation**.

## Customer Research

No findings recorded yet. **Pending Validation** for all six verticals (demand signals, willingness to pay, sales cycle, competitive landscape).

## Technology Preferences

**Accepted 2026-06-29 (DEC-010–015):**
- WhatsApp: **Meta Cloud API** (direct).
- Backend: **Python + FastAPI**. Frontend: **Next.js + TypeScript + Tailwind**.
- AI: **Anthropic Claude** — Sonnet 4.6 (reasoning) + Haiku 4.5 (intent classification).
- Database: **PostgreSQL + pgvector**. Auth: **Clerk**. Hosting: **Railway** (backend+DB) + **Vercel** (frontend).
- **Backend-first** development. Full detail in `documentation/`.

## How Sessions Run (Execution Mode — DEC-017, supersedes DEC-016)

Default is **Execution Mode** (CLAUDE.md §18): brief overview → implement immediately → explain only important architectural decisions → end-of-task summary (built / why / files / key concepts / bugs). Skip quizzes and long lessons unless asked; founder asks "Why?" for depth. Stop and warn before any important architectural mistake. Still update PROGRESS/TODOS/docs per task. Founder can switch back to Teacher Mode (DEC-016 style) any time.

## Coding Standards

See [CLAUDE.md](CLAUDE.md) Section 4 for the full standard. Key points worth remembering long-term:
- No comments explaining *what* code does — only non-obvious *why*.
- No speculative abstractions or premature config flags.
- No error handling for cases that cannot occur; validate only at real trust boundaries.

## UI/UX Principles

None established yet. **Pending Validation** — no frontend work has started.

## Documentation Standards

- Every `.claude/` file has exactly one job; content is not duplicated across files (see [CLAUDE.md](CLAUDE.md) Section 5).
- Each repository folder (`backend/`, `ai/`, `prompts/`, etc.) carries its own `README.md` explaining purpose, eventual contents, and rationale.
- Documentation is updated in the same session as the change that invalidates it, not deferred.

## Lessons Learned

None recorded yet. This section will capture lasting lessons (technical or business) as they're learned through building and customer feedback.

## Things to Avoid

- Inventing project facts (founder background, budget, timeline, tech choices) — these must be confirmed by the user, not assumed.
- Building features or infrastructure ahead of customer validation.
- Letting documentation drift from actual project state.
- Bundling unrelated changes or scope into a single piece of work.

## Future Ideas (not decisions)

These are speculative and unconfirmed — listed here only so they aren't lost, not because they've been decided:

- Expanding beyond AI Receptionist into other "AI employee" roles once the receptionist product is validated (per the AI Business Operating System vision).
- Expanding to additional verticals beyond the first validated one, using the same core product.
