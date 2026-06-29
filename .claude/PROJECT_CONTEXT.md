# PROJECT_CONTEXT.md

Current state of the HIRA project: what it is, who it's for, and what constraints apply. This file describes the present, not history (see `PROGRESS.md` for that) and not future plans (see `roadmap/` for that). Update this file whenever goals, scope, or constraints change — keep it current, not historical.

## What HIRA Is

HIRA is an AI Receptionist platform for WhatsApp-first businesses. It automatically responds to customer inquiries, answers FAQs from a business's own knowledge base, books and reschedules appointments, escalates complex conversations to a human, and aims to ensure businesses never miss a lead.

Long-term vision: an **AI Business Operating System** where businesses can "hire" AI employees across functions. The current focus is narrow and deliberate — becoming the best AI Receptionist first.

## Current MVP Scope

The MVP must:
- Reply to customers on WhatsApp
- Answer questions using a business knowledge base
- Book appointments into Google Calendar
- Reschedule appointments
- Escalate uncertain conversations to a human
- Store conversation history
- Run in **Assisted Mode** first (human reviews/approves AI actions); **Autonomous Mode** comes later

Status: **concept/foundation stage** — repository structure and documentation scaffolding have been created. No application code has been written yet.

## Target Customers

Six verticals are under evaluation to select **one** primary target for the first production version, based on market demand, willingness to pay, ease of sales, and product-market fit:
- Dental Clinics
- Beauty Salons
- Immigration & Study Abroad Consultants
- Gyms & Fitness Centers
- Real Estate Agencies & Property Consultants
- Cafés & Restaurants

Which vertical will be chosen: **Pending Validation**.

## Team / Founder

Solo founder, building with Claude acting as technical cofounder.

- **Founder**: B.Com (Hons.) student, beginner-level programmer, learning software engineering while building HIRA. No development team.
- **Goals**: build a real SaaS business, learn professional engineering deeply, build a GitHub portfolio, offer AI automation services on Fiverr, and understand every technology rather than copy code.
- **Optimization criteria for all technical decisions**: learning, simplicity, maintainability, production readiness — favor the option that maximizes long-term learning while still shipping an MVP quickly.

See `MEMORY.md` → Founder Profile for the durable version.

## Constraints

- Budget: **Low / bootstrapped** — no large budget; favor free and low-cost tiers.
- Team: **Solo** — no development team.
- Timeline / target launch date: **Unknown**
- Legal/compliance requirements (e.g., WhatsApp Business API policy, data privacy per target market): **Unknown — needs research before backend/database work begins**
- Existing tools/accounts already set up (WhatsApp Business API access, Google Cloud project, hosting accounts): **Unknown**

## Technology Decisions Made So Far

None yet. No stack, language, framework, hosting provider, or AI model/provider has been chosen. These are open decisions — see `DECISIONS.md` once populated.

## Open Questions

- Which of the six verticals will be the primary target?
- What WhatsApp integration path will be used (official WhatsApp Business API vs. a BSP provider)? **Unknown**
- What AI model/provider will power the conversation engine? **Unknown**
- Hosting/infrastructure provider? **Unknown**
- Pricing model? **Unknown**

## How to Keep This File Accurate

- When a vertical is chosen, update "Target Customers" and remove it from the open question.
- When a technology decision is made, log it in `DECISIONS.md` and reflect the outcome here under "Technology Decisions Made So Far."
- When MVP scope changes, update "Current MVP Scope" in the same session as the change.
- Do not let this file silently drift from reality — if a fact here is found to be stale or wrong, correct it immediately rather than leaving it.
