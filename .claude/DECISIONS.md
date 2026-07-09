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

---

## DEC-022 — Gemini is the default LLM provider (replacing Claude as default)

- **Date**: 2026-06-29
- **Category**: Technical
- **Decision**: Use Google **Gemini** (`gemini-2.0-flash` default) as the primary LLM provider, via the official **`google-genai`** SDK, implemented as `GeminiProvider` behind the existing `LLMProvider` interface. `LLM_PROVIDER=gemini`. ClaudeProvider and MockProvider remain available; switching is config-only.
- **Context**: Founder chose to replace Anthropic with Gemini for response generation.
- **Alternatives Considered**: Keep Claude default (DEC-021) — superseded by founder choice. Deprecated `google-generativeai` SDK — rejected for the current official `google-genai`.
- **Reasoning**: The provider-agnostic layer (DEC-021) made this a drop-in: one new class + factory entry + config, no orchestrator/business-logic change.
- **Trade-offs**: Gemini's API key project must have quota/billing enabled (observed `429 limit:0` on a project without quota). Embeddings remain local (DEC-020) — unaffected.
- **Status**: **Superseded by DEC-023 (2026-06-29)** — switched from Gemini to OpenRouter. GeminiProvider removed.
- **Review Date**: N/A.

---

## DEC-023 — OpenRouter is the default LLM provider (replaces Gemini)

- **Date**: 2026-06-29
- **Category**: Technical
- **Decision**: Use **OpenRouter** (OpenAI-compatible API) as the primary LLM provider via the official **`openai`** SDK with `base_url=https://openrouter.ai/api/v1`, implemented as `OpenRouterProvider` behind the existing `LLMProvider` interface. `LLM_PROVIDER=openrouter`, `OPENROUTER_MODEL` selects the model (any OpenRouter model id). GeminiProvider removed; ClaudeProvider + MockProvider intact.
- **Context**: Founder switched from Gemini to OpenRouter (one key, many models; avoids per-vendor billing setup).
- **Alternatives Considered**: Keep Gemini (DEC-022) — superseded by founder choice; Gemini key also had a quota-0 project.
- **Reasoning**: OpenRouter's OpenAI-compatible API + the provider abstraction made this a drop-in: one class + factory entry + config, no orchestrator/business-logic/prompt/retrieval change. One account fronts many models (incl. free tiers).
- **Trade-offs**: Adds OpenRouter as an intermediary (extra hop, their uptime/pricing). Embeddings remain local (DEC-020), unaffected.
- **Status**: **Superseded by DEC-024 (2026-06-29)** — switched to Groq after OpenRouter free-tier models proved unavailable/rate-limited. OpenRouterProvider removed.
- **Review Date**: N/A. Detail: `documentation/LLM_ORCHESTRATION.md`.

---

## DEC-024 — Groq is the default LLM provider (replaces OpenRouter)

- **Date**: 2026-06-29
- **Category**: Technical
- **Decision**: Use **Groq** (official `groq` SDK) as the primary LLM provider via `GroqProvider` behind the existing `LLMProvider` interface. `LLM_PROVIDER=groq`, `GROQ_MODEL` (default `llama-3.3-70b-versatile`). OpenRouterProvider + `openai` dep removed; Claude + Mock intact.
- **Context**: OpenRouter free-tier models were retired/unavailable or rate-limited (404/429) on the founder's account; Groq offers a fast free tier that worked on the first live call.
- **Alternatives Considered**: OpenRouter (DEC-023, superseded — free tier unreliable); Gemini (DEC-022, quota 0); Claude (available, needs Anthropic key/billing).
- **Reasoning**: The provider abstraction made this a drop-in (one class + factory + config); **live smoke test succeeded** (`llama-3.3-70b-versatile` answered correctly). No orchestrator/business-logic/prompt/retrieval change.
- **Trade-offs**: Groq model catalog is smaller (Llama/Mixtral/Gemma family); fine for the receptionist. Embeddings remain local (DEC-020).
- **Status**: Accepted — **live and verified.**
- **Review Date**: N/A. Detail: `documentation/LLM_ORCHESTRATION.md`.

---

## DEC-025 — Clerk JWT auth with JWKS verification; user→business_id resolution

- **Date**: 2026-06-29
- **Category**: Architecture
- **Decision**: Protect dashboard/API routes with Clerk. Verify RS256 session JWTs against Clerk's public **JWKS** (`CLERK_JWKS_URL`, optional issuer check) using PyJWT — no Clerk secret needed server-side. A `get_current_principal` dependency resolves the JWT `sub` (Clerk user id) to the local `User` row and returns a `Principal` carrying `business_id`; every protected route scopes by it. Cross-tenant access → `404`. First protected endpoints: `GET /api/v1/pending`, `POST /api/v1/messages/{id}/approve` (on top of `approve_and_send`).
- **Context**: Milestone 2. Existing multi-tenant architecture (DEC-013) and tenant helpers (DEC — tenant scoping) unchanged.
- **Alternatives Considered**: Verify via Clerk's API/secret key per request (network round-trip, slower — rejected; JWKS is the standard, stateless approach); hand-rolled auth (rejected — security risk for a beginner solo founder, per DEC-011).
- **Reasoning**: JWKS verification is stateless, fast, and the Clerk-recommended backend pattern. Token verification is injected as a dependency, so routes are testable without a live Clerk account (deterministic self-signed-JWT tests).
- **Trade-offs**: Requires `CLERK_JWKS_URL` configured to run live; a `User` row must exist per Clerk user (user provisioning/webhook is a later step).
- **Status**: Accepted (built & tested). Live use pending Clerk app credentials in `.env`.
- **Review Date**: N/A. Detail: `documentation/API.md`.

---

## DEC-026 — Next.js dashboard with mock-auth dev fallback (production-guarded)

- **Date**: 2026-07-01
- **Category**: UX
- **Decision**: Build the dashboard as specified (Next.js 15 App Router, TS, Tailwind v4, shadcn-style UI on Radix, TanStack Query, RHF/Zod, Lucide, Clerk). Auth uses real Clerk when `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set, and a **dev-only mock** otherwise; in production without Clerk the app renders an "auth not configured" screen rather than bypassing auth. A shared `AuthContext` abstracts Clerk vs mock so pages/API never call Clerk hooks directly. Typed API client centralizes auth token, retries, and errors; TanStack Query handles caching/optimistic updates/background refresh. Dashboard layers on the existing backend — no backend changes.
- **Context**: Milestone 3. Backend exposes only `/api/v1/pending` and approve; other pages render polished placeholders until endpoints exist.
- **Alternatives Considered**: Next.js 16 (installed by create-next-app) — **rejected**, pinned to 15 per spec (16 had breaking changes vs known conventions); shadcn CLI — skipped in favor of hand-authored primitives (Tailwind v4 + Radix) to avoid the interactive/config churn; hard build-time throw when Clerk missing — rejected (broke CI builds); replaced with a runtime auth-misconfigured screen.
- **Reasoning**: Mock fallback keeps dev unblocked without Clerk keys while the production guard preserves "never bypass auth in production." The `AuthContext` seam keeps Clerk swappable and pages testable without a live account.
- **Trade-offs**: Placeholder pages for missing endpoints; Node 26 local vs Node 22 CI (Next 15 supports both). Pinning Next 15 over the newer 16 to stay on known-stable ground.
- **Status**: Accepted — builds, typechecks, lints, tests pass; frontend CI job added.
- **Review Date**: N/A. Detail: `frontend/README.md`, `documentation/FRONTEND.md`.

---

## DEC-027 — Autonomous-mode auto-send completes the WhatsApp loop

- **Date**: 2026-07-03
- **Category**: Product
- **Decision**: In the background reply processor (`app/ai/processing.py`), when `business.mode == "autonomous"` the generated reply is sent immediately via the WhatsApp Cloud API (`send_text`) and marked `sent`/`failed` — no human approval. Assisted Mode (default) is unchanged (stores `pending_approval` for dashboard approval). No global `PHONE_NUMBER_ID` env: the sender number id is per-business (`businesses.whatsapp_phone_number_id`, from webhook metadata).
- **Context**: The webhook (verify/receive/signature/dedupe) and `send_text` already existed, but the loop required a human approval click. The requested end-to-end flow has no human node.
- **Alternatives Considered**: A global auto-send flag (rejected — `businesses.mode` already models this per-tenant); a global PHONE_NUMBER_ID (rejected — breaks multi-tenancy).
- **Reasoning**: Acts on the already-modelled `businesses.mode`; additive, preserves assisted behavior; no AI/retrieval/schema change.
- **Trade-offs**: Autonomous businesses send unreviewed replies — acceptable and opt-in per business; escalation/guardrails remain future work.
- **Status**: Accepted — code complete & tested (50 backend tests). Live round-trip pending Meta credentials/number (see WHATSAPP_INTEGRATION.md).
- **Review Date**: N/A.

---

## DEC-028 — Provider-agnostic AppointmentService with a CalendarProvider interface

- **Date**: 2026-07-08
- **Category**: Architecture
- **Decision**: New `app/calendar/` package, structured like `app/ai/llm/` (an interface + registry layer consumed by a sibling orchestration class): `providers/base.py` defines the `CalendarProvider` ABC (`get_availability`, `create_event`, `update_event`, `cancel_event`), provider-agnostic domain dataclasses (`TimeSlot`, `CalendarEventDraft`, `CalendarEventUpdate`, `CalendarEvent`), and a `CalendarError` hierarchy (`CalendarAuthError`, `CalendarConflictError`, `CalendarNotFoundError`, `CalendarProviderUnavailableError`). `providers/mock.py` (`MockCalendarProvider`) is the only registered implementation so far. `providers/__init__.py` exposes `get_calendar_provider(name)` — deliberately **not** `@lru_cache`d (unlike `get_llm_provider`/`get_embedding_provider`), because a real provider will be constructed per-business with that business's own credentials; caching by name alone would leak one business's calendar client to another. `service.py` (`AppointmentService`) is a class (not a function module, unlike `replies.py`/`provisioning.py`) holding `db`/`business_id`/`provider`/`calendar_id` as constructor state, with `list_availability`/`book_appointment`/`reschedule_appointment`/`cancel_appointment` methods — all tenant-scoped via `get_scoped` (`app/db/tenant.py`), all reachable only through the `CalendarProvider` interface (it never imports a vendor module). The provider is **injected**, not resolved from stored credentials inside the service — credential resolution (decrypting a business's OAuth token, picking which vendor class to build) is deliberately deferred to a not-yet-built `app/calendar/credentials.py`, so `AppointmentService` stays fully testable against `MockCalendarProvider` with no database-backed credential lookup.
- **Context**: A calendar-integration audit (this session) found `Appointment`/`CalendarCredential` exist in the schema with **zero** application code referencing them, and confirmed no OAuth, no service layer, no tool-calling capability in the LLM providers, and no frontend. The founder asked for the internal architecture to be designed and built *before* any Google OAuth work, specifically to avoid baking Google-specific assumptions into the booking logic.
- **Alternatives Considered**: A `GoogleCalendarService` built directly against the Google Calendar API (rejected — the explicit ask was "no Google-specific logic inside AppointmentService," and the audit found `app/ai/llm/`'s provider-swap pattern already solves exactly this problem elsewhere in the codebase); function-module style for `AppointmentService` matching `replies.py`/`provisioning.py` (rejected — every method needs both a `Session` and a resolved `CalendarProvider`; a class avoids threading both through every call site, a legitimate exception to the module convention).
- **Reasoning**: Mirrors an already-proven pattern (`app/ai/llm/`) rather than inventing a new one; keeps `AppointmentService` provider-agnostic by construction (it structurally cannot import a vendor module, since none exists in its import graph); defers OAuth/encryption/routes/frontend — none of which were requested yet — without leaving the interface or service in a half-built state.
- **Trade-offs**: `CalendarCredential` has no `provider` column, so once a second real vendor is added, one small additive migration is needed for `credentials.py` to know which provider a stored credential belongs to (flagged, not yet done — doesn't block the current single-provider-per-business shape, since `business_id` is already unique on that table). No idempotency key on `Appointment` yet either — a retried `book_appointment` call could theoretically double-book; flagged as a future additive column, not fixed now (out of scope: schema changes weren't authorized for this task).
- **Status**: Accepted — code complete & tested (17 new tests, 142 backend tests total). No OAuth, routes, or frontend built — deliberately out of scope for this phase.
- **Review Date**: Revisit when Google OAuth (Phase 2) is scheduled — decide the `CalendarCredential.provider` migration then.

---

## DEC-029 — Conversations API: limit/offset pagination envelope; "pending" is a derived filter

- **Date**: 2026-07-08
- **Category**: Architecture
- **Decision**: `GET /api/v1/conversations` and `GET /api/v1/conversations/{id}/messages` introduce the app's first pagination convention: `limit`/`offset` query params, response shape `{"data": [...], "meta": {"total", "limit", "offset"}}` — additive to the existing `{"data": ...}` envelope every other endpoint uses (a new top-level `meta` key, not a breaking change to the shape). The `status` filter chip set is `open | pending | closed`; `open`/`closed` map directly to `Conversation.status` (`active`/`closed`), but **`pending` is a derived, cross-cutting filter** — "has at least one outbound message with `status == "pending_approval"`" — not a `Conversation.status` value. Omitting `status` returns everything, including `escalated` conversations, which have no dedicated filter chip. Message-thread pagination returns the most recent `limit` messages (respecting `offset` to page further back) but reverses them to oldest-first before responding, matching `app/ai/orchestrator.py`'s existing `_load_history` convention.
- **Context**: Building the Inbox (`GET /conversations`, `/{id}`, `/{id}/messages`) required a pagination shape and filter semantics that didn't exist anywhere in the codebase yet — every prior list endpoint (`/kb`, `/pending`) returns everything unpaginated. The frontend's three requested filter chips (Open/Pending/Closed) don't map 1:1 onto the three real `Conversation.status` values (`active/escalated/closed`) — "pending" doesn't exist as a conversation-level state at all; it's inherently a `Message`-level fact.
- **Alternatives Considered**: Cursor-based pagination (rejected — `limit`/`offset` is simpler, sufficient at this scale, and boring/well-understood per CLAUDE.md's technology philosophy; revisit only if conversation volume ever makes offset pagination's performance a real problem); adding a fourth "Escalated" filter chip to cover all three `Conversation.status` values (rejected — not requested, and escalated conversations remain visible under "All"); a `Conversation.status` value of `"pending"` (rejected — would require a schema/migration change and conflates a per-message fact with per-conversation state; the derived-filter approach needed no migration).
- **Reasoning**: Keeps this additive — no schema change, no migration, reuses `tenant_query`/`get_scoped` and the existing envelope convention with one backward-compatible extension (`meta`). The oldest-first-after-fetching-newest-first pattern for messages reuses an established convention instead of inventing a second one.
- **Trade-offs**: `escalated` conversations are invisible under every filter chip except "All" — a business owner filtering to "Open" won't see a conversation a human needs to look at *because* it's escalated. Acceptable for v1 (matches exactly what was asked — three chips, not four) but worth revisiting if/when the escalation-handling roadmap item (`ARCHITECTURE.md` §15 item 3) is built, since escalated conversations arguably deserve their own visibility, not just inclusion in an unfiltered view.
- **Status**: Accepted — code complete & tested (20 new backend tests, 162 total; 12 new frontend tests, 55 total).
- **Review Date**: Revisit the `escalated` visibility trade-off when human-handoff/escalation (§15 item 3) is built.

---

## DEC-030 — Pending Approvals V2: editable drafts, reject, regenerate, and manual escalation, all sharing one tenant-scoped action module

- **Date**: 2026-07-09
- **Category**: Architecture
- **Decision**: `POST /messages/{id}/approve` (existing) gained four siblings — `PATCH /messages/{id}/draft`, `POST /messages/{id}/reject`, `POST /messages/{id}/regenerate`, `POST /messages/{id}/escalate` — all added to `backend/app/services/replies.py` (renamed in scope from "approve and send" to every pending-draft action) behind a single shared `_get_pending_reply()` lookup (tenant-scoped via `get_scoped`, raises `ValueError` unless the message is this business's `outbound`/`pending_approval` row — including `approve_and_send` itself, refactored onto the same helper). Every route in `dashboard.py` maps that `ValueError` to `404`, identical to the pre-existing approve endpoint's "don't reveal whether it exists for another tenant" convention. `Message.status` gained two new string values, `rejected` and `escalated` (no migration — the column has no CHECK constraint, per the original "status fields are plain strings for MVP flexibility" design). `regenerate_draft()` calls the unmodified `orchestrator.generate_reply()` — the same function the WhatsApp webhook and the AI Playground already call — against the customer message that originally triggered the draft (found via `_last_inbound_before`, using `<=` rather than `<` because Postgres's `now()` is fixed for a transaction's duration, so a message and the reply generated for it in the same transaction can share a timestamp), and replaces only that message's `body`/`ai_meta` in place. `escalate_reply()` creates an `Escalation` row (the table has existed since the initial migration with zero application code referencing it until now) with `reason="other"` and marks the parent `Conversation.status = "escalated"` — a value the schema has modeled since the same initial migration but nothing had ever assigned. `GET /pending` gained two additive fields, `customer` (joined via the conversation) and `conversation_preview` (the most recent inbound message in that conversation), reusing the same `DISTINCT ON` "latest message per conversation" pattern DEC-029's `conversations.py` already established, rather than inventing a second way to compute a preview.
- **Context**: Sprint 27 turns the Pending Replies queue from a bare approve button into the intended AI-copilot loop (customer → AI drafts → human edits/approves/rejects/regenerates/escalates → reply sent). The four new actions and the `/pending` payload enrichment needed a lookup/validation pattern; the approve endpoint's existing tenant-scoping and 404-on-invalid-state convention already solved that problem.
- **Alternatives Considered**: A `409 Conflict` for "message already approved" instead of `404` — rejected, to stay consistent with the existing approve endpoint's deliberate choice not to distinguish "not found" from "not yours" from "no longer pending" (all three are equally uninformative to a caller who shouldn't be probing another tenant's data). A dedicated `escalation_reason` request body for `POST /messages/{id}/escalate` — rejected as unrequested scope; no UI was asked to collect a reason, so the endpoint takes no body and defaults to `"other"`, one of the four reasons the schema already models. Filtering `_last_inbound_before` with strict `<` — reverted after it failed in tests: within one uncommitted transaction, `now()` is fixed, so an inbound message and the outbound draft it triggered can share a timestamp; `<=` is safe here specifically because the query already filters `direction == "inbound"`, so it can never match the (outbound) draft itself.
- **Reasoning**: Every new endpoint reuses an already-proven pattern (tenant scoping via `get_scoped`, the approve endpoint's error-hiding convention, the orchestrator's unmodified reply pipeline, DEC-029's latest-message-per-conversation query shape) rather than introducing a second way to do any of these things. Adding string values to an already-unconstrained status column, and writing to two long-modeled-but-unused schema elements (`escalations`, `Conversation.status = "escalated"`), kept the whole sprint migration-free.
- **Trade-offs**: There is still no `GET /escalations` list or `POST /escalations/{id}/resolve` endpoint — `Escalation` rows are now created but not yet visible or actionable anywhere in the dashboard; an operator who escalates a conversation today has no in-app way to see the resulting queue (flagged in `ARCHITECTURE.md` §15 item 3, not built — out of scope for this sprint, which was about the Pending queue, not a new Escalations page). `regenerate_draft()`'s history load (`orchestrator._load_history`) still includes the very draft being replaced as a prior "assistant" turn, since regenerating doesn't delete or exclude it first — reusing the pipeline unmodified was preferred over adding history-filtering logic for a single caller.
- **Status**: Accepted — code complete & tested (33 new backend tests, 195 total; backend endpoints also smoke-tested live against the real dev database and a real Groq LLM call, then fully reverted; 20 new/updated frontend tests, 68 total). `ruff check`/`ruff format` (scoped to touched files only — 13 pre-existing files already failed `ruff format --check` on `main` before this sprint and were left untouched), ESLint, `tsc --noEmit`, and `next build` all clean.
- **Review Date**: When Escalations gets its own list/resolve endpoint and dashboard surface — revisit whether `reason="other"` should become an operator-chosen value at that point.

---

## DEC-031 — CRM foundation: `Lead` (one per customer per business) + append-only `LeadEvent` timeline, new migration

- **Date**: 2026-07-09
- **Category**: Architecture
- **Decision**: New migration adds two tables. `leads`: `id`, `business_id` (FK → `businesses.id`, `ON DELETE CASCADE`, indexed — required for `tenant_query`/`get_scoped`, which reject any model without a direct `business_id` column), `customer_id` (FK → `customers.id`, `ON DELETE CASCADE`), `stage` (`String(32)`, default `"new"`, **no CHECK constraint** — same "plain string, no DB-level enum" convention as `Message.status`/`Conversation.status`; validated instead at the API boundary via a Pydantic `Literal["new","contacted","qualified","proposal_sent","negotiation","won","lost"]`), `source` (`String(64)`, nullable, free text — not validated against a fixed set, unlike `stage`), `estimated_value` (`Numeric(12, 2)`, nullable), `notes` (`Text`, nullable), `next_follow_up_at` (`DateTime`, nullable), `assigned_to` (FK → `users.id`, `ON DELETE SET NULL`, nullable — same shape as `Escalation.resolved_by`), `created_at`/`updated_at`. `UNIQUE(business_id, customer_id)` — **one lead per customer per business for the MVP**; a repeat inquiry updates the existing lead rather than creating a second one. Composite index `ix_leads_business_stage (business_id, stage)` for pipeline-board-style "list leads in stage X" queries, mirroring `ix_conversations_business_status_last`.
  `lead_events`: `id`, `lead_id` (FK → `leads.id`, `ON DELETE CASCADE`, indexed), `type` (`String(32)` — `lead_created | stage_change | notes_updated | follow_up_set | assigned`), `from_value`/`to_value` (`Text`, nullable — `Text` rather than `String` because `notes_updated` events store full note content, not just short codes), `note` (`Text`, nullable, currently unused by any event type the app writes — reserved for a future caller-supplied annotation), `created_at`. **No `business_id` column** — this is the first tenant-owned-adjacent table without one; every query reaches it by joining through `Lead.business_id`, never via `tenant_query`/`get_scoped` directly (documented in `app/services/leads.py`). **Append-only**: application code only ever inserts `LeadEvent` rows; nothing updates or deletes one once written (`ON DELETE CASCADE` from the parent `Lead` is the only way a row disappears, when the whole lead is deleted).
  Events are logged only for `stage`, `notes`, `next_follow_up_at`, and `assigned_to` changes (each only when the new value actually differs from the old one) — not for `source` or `estimated_value`, which are treated as descriptive lead attributes rather than pipeline-progression activity. `PATCH /leads/{id}` distinguishes "field omitted" from "field explicitly set to null" via Pydantic's `model_fields_set` (not plain `is not None`), so `assigned_to`/`next_follow_up_at`/`notes`/`source`/`estimated_value` can all be explicitly cleared — a real gap the simpler "all-optional-fields-default-None" pattern used by `PATCH /kb/{id}` doesn't have to solve, since none of that endpoint's fields are nullable-and-clearable.
  The customer timeline (`GET /customers/{id}/timeline`) merges `Message` rows (via the customer's conversations) and `LeadEvent` rows (via the customer's lead) in Python — fetch the most recent `offset + limit` rows from each source ordered newest-first, merge, slice to the requested page — rather than a SQL `UNION ALL` across two structurally different row shapes. `meta.total` is the sum of two independent `COUNT(*)` queries.
- **Context**: Sprint 28 (CRM Foundation) explicitly required a `Lead` model — the only schema the codebase had for "customer relationship" state before this was `Conversation.status`. This is the first sprint since the founding schema (`DECISIONS.md` DEC-013) to add new tables rather than reuse or extend existing ones, so per the standing execution policy this was **stopped and escalated** rather than the schema being invented unilaterally; the founder specified the exact shape above (one Lead per customer, `LeadEvent` for history, which fields are event-worthy) before any code was written.
- **Alternatives Considered**: Multiple leads per customer over time (rejected by the founder — MVP scope is one lead per customer, updated in place); a `Conversation.status`-style single mutable field with no history table (rejected — the sprint explicitly asked for a customer timeline aggregating "CRM events," which requires an append-only log, not just current state); a SQL `UNION ALL` for the timeline query (considered for single-round-trip efficiency, but `Message` and `LeadEvent` don't share a natural column signature — reconciling nullable placeholder columns and type-casting untyped `NULL`s across the two `SELECT`s added real complexity for a merge that, at MVP data volumes, a two-query-then-Python-merge handles correctly and far more simply, consistent with "boring solution over clever" per `CLAUDE.md` §2); giving `LeadEvent` its own `business_id` (rejected by the founder's explicit field list — enforced instead by always joining through `Lead`).
- **Reasoning**: The one-lead-per-customer constraint keeps the MVP model simple and matches how `Customer` itself is already unique per `(business_id, wa_phone)`. Keeping `stage` an unconstrained string (validated only at the API layer) matches every other status field in the schema and avoids a second migration if a stage is ever added/renamed. The append-only `LeadEvent` table is the smallest structure that satisfies "customer timeline aggregates CRM events" without mutating history in place — mirroring how `Message` rows are themselves never edited after creation (edits go through separate app-level actions, not row mutation of the historical record) once sent/rejected/escalated.
- **Trade-offs**: One lead per customer means there's no way to represent "this customer had two separate sales cycles" without deleting and recreating the lead (losing its `LeadEvent` history via cascade) — acceptable for MVP per the founder's explicit choice, revisit if repeat-business tracking becomes a real need. The Python-merge timeline re-fetches up to `offset + limit` rows from both sources on every page request rather than a single indexed query — fine at MVP data volumes (mirrors the existing `_load_history`/conversation-message-thread pattern's own "fetch more, process in memory" style), but would need revisiting (most likely the `UNION ALL` approach that was rejected above) if a single customer's timeline ever grows into the thousands of rows. `LeadEvent.note` is reserved but currently written by nothing — a small amount of speculative schema, kept because it's a free column on an already-being-created table, not a separate migration.
- **Status**: Accepted — schema, service layer, API, and frontend implemented and tested this session (see `.claude/PROGRESS.md` for test counts).
- **Review Date**: Revisit one-lead-per-customer and the Python-merge timeline if/when multi-cycle lead tracking or timeline scale becomes a real requirement.
