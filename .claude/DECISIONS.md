# DECISIONS.md

Permanent decision log for HIRA — architectural, product, and business decisions with lasting consequence. This is an append-only history.

**Rules:**
- Never delete a decision. History is never rewritten.
- If a decision changes, mark the old one **Superseded** (leave it intact, note which decision replaces it) and add a new decision that references the one it supersedes.
- Record only decisions with lasting consequence — not implementation trivia.
- Update this file whenever an important decision is made.
- Never invent reasoning or alternatives; if something wasn't actually considered, say so.

Each entry uses: Decision ID · Date · Category · Decision · Context · Alternatives Considered · Reasoning · Trade-offs · Status · Review Date.

---

## DEC-001 — Long-term vision is an AI Business Operating System

- **Date**: 2026-06-29
- **Category**: Business
- **Decision**: HIRA's long-term vision is to become an AI Business Operating System where businesses can "hire" AI employees across multiple business functions.
- **Context**: Setting the north star that gives all near-term work a direction, while keeping near-term scope narrow.
- **Alternatives Considered**: None formally recorded. The vision was stated as a founding premise.
- **Reasoning**: A large, expandable vision provides strategic direction and framing for fundraising/positioning, while still allowing a deliberately narrow first product.
- **Trade-offs**: A broad vision risks scope creep if not disciplined; mitigated by DEC-002 and DEC-003 which keep the first product narrow.
- **Status**: Accepted
- **Review Date**: Pending Validation

---

## DEC-002 — First product is an AI Receptionist

- **Date**: 2026-06-29
- **Category**: Product
- **Decision**: The first product is an AI Receptionist for WhatsApp-first businesses (responds to inquiries, answers FAQs from a knowledge base, books/reschedules appointments, escalates to humans, stores conversation history).
- **Context**: The AI Business Operating System (DEC-001) is too large to build at once. A focused first product is needed to enter the market.
- **Alternatives Considered**: Building broader "AI employee" functionality up front. Rejected in favor of focus.
- **Reasoning**: Receptionist is a concrete, high-frequency pain point with clear value (never miss a lead) and a measurable outcome (booked appointments). It is a wedge into the larger vision.
- **Trade-offs**: Narrow scope may undersell the larger vision to some stakeholders; accepted in exchange for a shippable, validatable product.
- **Status**: Accepted
- **Review Date**: Pending Validation

---

## DEC-003 — MVP-first philosophy

- **Date**: 2026-06-29
- **Category**: Product
- **Decision**: Build the smallest possible MVP. No feature ships ahead of demonstrated need.
- **Context**: Early-stage product with unvalidated assumptions; building too much too early wastes time and money.
- **Alternatives Considered**: Building a feature-rich product before launch. Rejected.
- **Reasoning**: A minimal product reaches real customers faster and exposes wrong assumptions cheaply. Aligns with CLAUDE.md development and startup philosophy.
- **Trade-offs**: A minimal product may feel incomplete to some early prospects; accepted in exchange for speed and learning.
- **Status**: Accepted
- **Review Date**: Pending Validation

---

## DEC-004 — Customer validation before scaling

- **Date**: 2026-06-29
- **Category**: Business
- **Decision**: Validate product-market fit with real customers before scaling features, verticals, or infrastructure.
- **Context**: Six candidate verticals and many possible features exist; resources are limited.
- **Alternatives Considered**: Scaling/expanding on assumption before validation. Rejected.
- **Reasoning**: Scaling an unvalidated product multiplies wasted effort. Validation de-risks the larger investments.
- **Trade-offs**: Slower apparent growth in the short term; accepted to avoid building the wrong thing at scale.
- **Status**: Accepted
- **Review Date**: Pending Validation

---

## DEC-005 — WhatsApp-first approach

- **Date**: 2026-06-29
- **Category**: Product
- **Decision**: HIRA is WhatsApp-first — the primary channel where the AI Receptionist meets customers is WhatsApp.
- **Context**: Target businesses' customers already communicate via WhatsApp; meeting them there lowers adoption friction.
- **Alternatives Considered**: Web chat widget, SMS, or multi-channel from the start. Not chosen for the first product (multi-channel remains a possible future direction, not a decision).
- **Reasoning**: Focusing on one high-adoption channel keeps the MVP small and matches where the target customers' demand already exists.
- **Trade-offs**: Dependency on WhatsApp Business API rules and pricing; single-channel coverage. The specific integration path (official WhatsApp Business API vs. a BSP/provider) is **not yet decided** — Pending Validation.
- **Status**: Accepted
- **Review Date**: Pending Validation

---

## DEC-006 — Research six candidate verticals; select one primary

- **Date**: 2026-06-29
- **Category**: Business
- **Decision**: Research six industries and select **one** primary vertical for the first production version. The six are: Dental Clinics, Beauty Salons, Immigration & Study Abroad Consultants, Gyms & Fitness Centers, Real Estate Agencies & Property Consultants, Cafés & Restaurants.
- **Context**: A focused go-to-market requires a single beachhead vertical rather than spreading thin.
- **Alternatives Considered**: Launching horizontally across all six at once. Rejected per DEC-003/DEC-004.
- **Reasoning**: Selection criteria are market demand, willingness to pay, ease of sales, and product-market fit. One vertical allows tailored prompts, messaging, and sales.
- **Trade-offs**: Narrowing may exclude a vertical that later proves strong; mitigated by keeping the core product vertical-agnostic so expansion is cheap.
- **Status**: Accepted — chosen vertical is **Pending Validation**.
- **Review Date**: When customer research concludes.

---

## DEC-007 — Git + GitHub from day one

- **Date**: 2026-06-29
- **Category**: Operations
- **Decision**: Use Git for version control and GitHub as the remote from the start of the project.
- **Context**: Establishing professional engineering practices early, before significant code exists.
- **Alternatives Considered**: Deferring version control until later, or using a different host (GitLab, Bitbucket). Not chosen.
- **Reasoning**: Version control from day one preserves history, enables review, and supports the documentation-first workflow.
- **Trade-offs**: Minor upfront setup overhead. **Note**: as of this entry the working directory is not yet a Git repository — initialization is pending and tracked in `TODOS.md`.
- **Status**: Accepted (implementation pending)
- **Review Date**: N/A

---

## DEC-008 — Claude project memory via the `.claude/` directory

- **Date**: 2026-06-29
- **Category**: Operations
- **Decision**: Maintain a persistent, file-based project memory system in `.claude/` (CLAUDE.md, PROJECT_CONTEXT.md, MEMORY.md, PROGRESS.md, TODOS.md, DECISIONS.md) that Claude reads and updates across sessions.
- **Context**: Cross-session continuity is needed so context and decisions aren't re-explained each session.
- **Alternatives Considered**: Relying on conversation context alone (lost between sessions) or external doc tools. Not chosen.
- **Reasoning**: A version-controlled, in-repo memory keeps the source of truth next to the code and survives session boundaries.
- **Trade-offs**: Requires discipline to keep files current; mitigated by explicit update rules in CLAUDE.md Section 12.
- **Status**: Accepted
- **Review Date**: N/A

---

## DEC-009 — Documentation-first development

- **Date**: 2026-06-29
- **Category**: Operations
- **Decision**: Establish structure and documentation before writing application code; keep documentation updated in the same session as the change that affects it.
- **Context**: The project began by building repository structure and documentation scaffolding ahead of any code.
- **Alternatives Considered**: Code-first, documenting later. Rejected — deferred docs tend to drift or never get written.
- **Reasoning**: Clear structure and intent reduce rework and make the codebase navigable as it grows. Aligns with CLAUDE.md documentation standards.
- **Trade-offs**: Slower start before the first line of code; accepted for long-term clarity and maintainability.
- **Status**: Accepted
- **Review Date**: N/A

---

> The decisions below (DEC-010 to DEC-015) are the MVP engineering plan. **Accepted 2026-06-29** by the founder after confirming beginner background, the two-language (Python + TypeScript) reality, backend-first development, and managed auth via Clerk. Full detail lives in `documentation/`.

## DEC-010 — WhatsApp integration: Meta Cloud API (direct)

- **Date**: 2026-06-29
- **Category**: Technical
- **Decision**: Use the Meta WhatsApp Cloud API directly for the MVP; optionally spike on the Twilio sandbox first. Revisit 360dialog at multi-tenant scale.
- **Context**: AI receptionist traffic is mostly inbound service replies inside the free 24h window (1,000 free service conversations/month); per-message markup matters little for MVP, more at scale.
- **Alternatives Considered**: Twilio (fastest setup, +$0.005/msg markup, lock-in); 360dialog (€49/mo flat, no markup, strong for multi-number provisioning later); other BSPs (more lock-in/less control).
- **Reasoning**: Best long-term cost and control, cheapest Indian rates, highest learning value (the real platform, not an abstraction). Loses only on setup speed — mitigated by an optional Twilio-sandbox spike.
- **Trade-offs**: Harder initial setup (Meta Business verification, embedded signup); HMAC/webhook plumbing is on us.
- **Status**: Accepted (2026-06-29)
- **Review Date**: At multi-tenant scaling (reconsider 360dialog). Full detail: `documentation/WHATSAPP_INTEGRATION.md`.

## DEC-011 — MVP technology stack

- **Date**: 2026-06-29
- **Category**: Technical
- **Decision**: Python + FastAPI backend; Anthropic Claude (Sonnet 4.6 reasoning, Haiku 4.5 classification); PostgreSQL + pgvector; Next.js + TypeScript + Tailwind frontend; Clerk auth; Railway (backend+DB) + Vercel (frontend); Google Calendar API.
- **Context**: Solo founder optimizing for learning, fast development, low cost, production readiness.
- **Alternatives Considered**: Node/NestJS backend (unifies language — recommended fallback if founder prefers all-TS); Supabase all-in-one (fewer vendors, more lock-in); dedicated vector DB (rejected, pgvector suffices).
- **Reasoning**: Python is AI-native; pgvector avoids a separate vector service; managed auth/hosting keeps a solo founder productive and secure.
- **Trade-offs**: Two languages (Python + TS). **Assumes founder is willing to learn Python/TS — founder background is Unknown; confirm before accepting.**
- **Status**: Accepted (2026-06-29)
- **Review Date**: Before Sprint 1 start. Full detail: `documentation/TECH_STACK.md`.

## DEC-012 — MVP system architecture

- **Date**: 2026-06-29
- **Category**: Architecture
- **Decision**: Webhook handler → async conversation orchestrator (intent → KB/tool/escalate) → Assisted-Mode approval gate → outbound send; Postgres system of record; dashboard via REST + Clerk JWT. Vertical-agnostic core.
- **Context**: Implements the Assisted-Mode MVP scope.
- **Alternatives Considered**: Synchronous webhook processing (rejected — must return 200 fast); monolith vs. services (monolith chosen — fewer moving parts for solo founder).
- **Reasoning**: Async processing protects against Meta retries; escalation-on-uncertainty and AI audit logging address AI failure modes; multi-tenant scoping enforced at the data layer.
- **Trade-offs**: Background processing adds some complexity vs. a pure request/response app; justified by webhook reliability needs.
- **Status**: Accepted (2026-06-29)
- **Review Date**: N/A. Full detail: `documentation/ARCHITECTURE.md`.

## DEC-013 — Database design

- **Date**: 2026-06-29
- **Category**: Architecture
- **Decision**: PostgreSQL schema: businesses, users, customers, conversations, messages, kb_entries (pgvector), appointments, escalations, calendar_credentials; tenant-scoped by business_id; Assisted/Autonomous modeled via flags, not schema changes.
- **Context**: Multi-tenant system of record for the MVP.
- **Alternatives Considered**: Separate vector store (rejected); per-tenant databases (rejected — overkill at MVP scale).
- **Reasoning**: Relational fit; additive expansion path to AI-OS (agents/roles) and multi-number without breaking changes.
- **Trade-offs**: Shared-schema multi-tenancy requires disciplined scoping (mitigated in DEC-012).
- **Status**: Accepted (2026-06-29)
- **Review Date**: N/A. Full detail: `documentation/DATABASE.md`.

## DEC-014 — REST API design

- **Date**: 2026-06-29
- **Category**: Architecture
- **Decision**: Versioned `/api/v1` REST API; Clerk JWT for dashboard, Meta signature for webhook; consistent data/error envelope; endpoints for conversations/inbox, approvals, escalations, appointments, KB, settings, users.
- **Context**: Contract between the Next.js dashboard and the backend.
- **Alternatives Considered**: GraphQL (rejected — unnecessary complexity for MVP); unversioned API (rejected — future breakage risk).
- **Reasoning**: REST is simple, well-understood, auto-documented by FastAPI; versioning protects clients.
- **Trade-offs**: Some over-fetching vs. GraphQL; acceptable at MVP scale.
- **Status**: Accepted (2026-06-29)
- **Review Date**: N/A. Full detail: `documentation/API.md`.

## DEC-015 — Frontend design

- **Date**: 2026-06-29
- **Category**: UX
- **Decision**: Next.js dashboard for business owner/staff: Dashboard, Inbox (core Assisted-Mode surface), Calendar, Knowledge Base, Settings; desktop-first; data via `/api/v1`.
- **Context**: Customers stay in WhatsApp; the business needs a control/approval surface.
- **Alternatives Considered**: No dashboard / config-by-message (rejected — no approval or review surface); native app (rejected — premature).
- **Reasoning**: The Inbox approval flow is essential to Assisted Mode; a web dashboard is the fastest learnable, production-ready option.
- **Trade-offs**: Building a UI adds scope vs. backend-only; required by Assisted Mode.
- **Status**: Accepted (2026-06-29)
- **Review Date**: N/A. Full detail: `documentation/FRONTEND.md`.

---

## DEC-016 — Three-stage feature workflow (Explain → Build → Review)

- **Date**: 2026-06-29
- **Category**: Operations
- **Decision**: Every feature is built in three mandatory stages — Stage 1 Explain (why, architecture fit, concepts, alternatives, beginner mistakes) before any code; Stage 2 Build (small focused commits, no unnecessary abstractions); Stage 3 Review (explain files/logic/decisions/extensions, update all docs + memory + progress, capture learnings, suggest commit message). Codified in `CLAUDE.md` §18.
- **Context**: The founder is a beginner learning professional software engineering while building HIRA; every session must optimize for both shipping and teaching.
- **Alternatives Considered**: Build-only (faster but no learning) and explain-only (learning without shipping). Both rejected — the founder's stated goal requires both simultaneously.
- **Reasoning**: Structured teaching around real implementation builds durable understanding ("understand every technology, not copy code") while still producing a shipped product and a portfolio.
- **Trade-offs**: Slower per-feature throughput due to explanation overhead; explicitly accepted as the point of the project.
- **Status**: **Superseded by DEC-017 (2026-06-29).** Founder moved to Execution Mode to ship faster; can switch back to Teacher Mode on request.
- **Review Date**: N/A

---

## DEC-017 — Switch to Execution Mode (supersedes DEC-016)

- **Date**: 2026-06-29
- **Category**: Operations
- **Decision**: Default working mode is **Execution Mode**: brief 2–5 min overview → implement immediately → explain only important architectural decisions while coding → end-of-task summary (what was built, why it matters, files changed, key concepts, bugs fixed). Skip quizzes/knowledge-checks/long lessons unless requested. Stop and warn before any important architectural mistake. Codified in CLAUDE.md §18.
- **Context**: Foundation tasks (S1-01–03) are done; founder now prioritizes building HIRA quickly while keeping high engineering quality. The teaching-heavy three-stage workflow (DEC-016) was too slow for that priority.
- **Alternatives Considered**: Keep DEC-016 teacher mode (too slow for shipping); drop explanations entirely (loses the learning goal). Execution Mode is the middle path.
- **Reasoning**: Founder can always ask "Why?" for depth; defaulting to lean delivery maximizes shipping speed without abandoning understanding of important parts.
- **Trade-offs**: Less proactive teaching; relies on the founder to pull deeper explanations when wanted.
- **Status**: Accepted
- **Review Date**: N/A

---

## DEC-018 — Autonomous Execution Mode

- **Date**: 2026-06-29
- **Category**: Operations
- **Decision**: Claude operates autonomously for routine engineering — no approval needed to create/edit/delete files, install dev deps, run tests/linters, create+apply migrations, commit, refactor, fix bugs, improve non-behavioral architecture, or update docs/memory/progress. Stop and ask only for: (1) business decision changes, (2) product feature changes, (3) a required paid service, (4) destructive operations risking data loss, (5) credentials/API-keys/billing, (6) legal/security/privacy decisions, (7) multiple valid architectures with significant trade-offs. Codified in CLAUDE.md §18.
- **Context**: Founder prioritizes momentum/shipping; per-task approval prompts were slowing routine work after the foundation is in place.
- **Alternatives Considered**: Keep per-task approval (slower); full autonomy with no stop-list (too risky for business/legal/cost). The seven-case stop-list is the balance.
- **Reasoning**: Reversible, low-risk work should just happen; irreversible or business/cost/legal/security-significant decisions still require the founder.
- **Trade-offs**: Less oversight on routine changes; mitigated by small commits + CI + the stop-list, all reversible via Git.
- **Status**: Accepted
- **Review Date**: N/A

---

## DEC-019 — Prioritize end-to-end AI receptionist over auth/dashboard

- **Date**: 2026-06-29
- **Category**: Product
- **Decision**: Build the core AI loop first — receive WhatsApp message → retrieve from knowledge base → generate response → send back to WhatsApp. Pause Clerk auth (S1-05) and dashboard work until that loop works end to end. Reorder Sprint 1 accordingly (S1-07, S1-08, S1-09 next).
- **Context**: Founder is obtaining an Anthropic API key and wants the product's differentiating capability proven before supporting infrastructure.
- **Alternatives Considered**: Continue strict S1 numeric order (auth before AI) — rejected; auth is supporting infrastructure, not the value proposition.
- **Reasoning**: The AI receptionist is the MVP's core value; proving it end to end de-risks the product fastest. Auth/dashboard can follow.
- **Trade-offs**: The AI loop will run without the dashboard approval UI initially; Assisted-Mode approval surfaces later. Acceptable for proving the loop.
- **Status**: Accepted
- **Review Date**: When the E2E AI loop works.

---

## DEC-020 — Local open-source embeddings (BAAI/bge-small-en-v1.5) behind an EmbeddingProvider abstraction

- **Date**: 2026-06-29
- **Category**: Architecture
- **Decision**: Knowledge-base embeddings are generated locally by `BAAI/bge-small-en-v1.5` (384 dims) via `fastembed` (ONNX, no PyTorch). All KB indexing/retrieval depend only on an `EmbeddingProvider` interface; provider is selected by config (`EMBEDDING_PROVIDER`, default `local_bge`). Anthropic/Claude handles reasoning only, not embeddings.
- **Context**: Founder priorities — low cost, learning, simplicity, privacy, flexibility; no second paid API during MVP.
- **Alternatives Considered**: Voyage AI / OpenAI embeddings (higher quality, but paid + another key/vendor — rejected for MVP); sentence-transformers (pulls heavy PyTorch — rejected; fastembed is lighter). bge-small chosen over larger bge variants for speed/footprint at acceptable quality.
- **Reasoning**: Local embeddings are free, private, no extra credential, and good enough for KB semantic search. The abstraction keeps a hosted provider a config + small class away.
- **Trade-offs**: Lower retrieval quality than top hosted models; CPU inference latency; model download on first use; schema dimension (384) is coupled to the model — changing to a different-dimension provider needs a migration.
- **Status**: Accepted
- **Review Date**: If retrieval quality proves insufficient in pilot.

---

## DEC-021 — Provider-agnostic LLM layer (LLMProvider; Claude + Mock)

- **Date**: 2026-06-29
- **Category**: Architecture
- **Decision**: All reasoning/response generation goes through an `LLMProvider` interface. `MockProvider` (default, no key) and `ClaudeProvider` (Anthropic) are implemented; provider selected by `LLM_PROVIDER` config. Business logic (orchestrator, prompts, processing) never imports a vendor SDK. Going live = add `ANTHROPIC_API_KEY` + set `LLM_PROVIDER=claude`.
- **Context**: Build the full AI loop before the API key arrives; keep vendor lock-in out; enable offline tests.
- **Alternatives Considered**: Call the Anthropic SDK directly from the orchestrator (vendor lock-in, untestable without a key — rejected).
- **Reasoning**: The abstraction lets the whole loop run/test with a mock today and swap to Claude (or OpenAI/Gemini/OpenRouter/local later) by config alone. Matches the EmbeddingProvider pattern (DEC-020).
- **Trade-offs**: A thin abstraction layer over the SDK; worth it for testability and flexibility. Provider-specific features (e.g. tool use) will need interface extension when needed.
- **Status**: Accepted
- **Review Date**: N/A. Detail: `documentation/LLM_ORCHESTRATION.md`.
