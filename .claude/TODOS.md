# TODOS.md

Living execution backlog for HIRA. Tasks move between sections as their status changes — they are never deleted or rewritten. Completed work is appended to the Completed section, never removed.

**Rules:**
- Never delete completed tasks; move tasks between sections rather than rewriting history.
- Keep priorities realistic.
- Do not add speculative features to the MVP — implementation tasks only enter the backlog after the relevant validation/decision is done.
- Customer validation tasks are kept separate from engineering tasks.
- Blockers are highlighted clearly in the Blocked section with what they wait on.

Task fields: ID · Title · Description · Priority · Category · Estimated effort · Dependencies · Status · Success criteria.

Categories: Business · Product · Technical · Architecture · Research · Operations · Validation.
Priority: P0 (critical) · P1 (high) · P2 (medium) · P3 (low).

---

## Current Sprint

> Focus: prepare for the MVP — validate customers, select the first vertical, finalize architecture, and set up the development environment. No application/implementation tasks until validation completes.

### TASK-001 — Define founder & project constraints
- **Description**: Capture currently-unknown facts in `PROJECT_CONTEXT.md`: founder technical background, budget, timeline/target launch, existing accounts (WhatsApp Business API, Google Cloud, hosting).
- **Priority**: P0
- **Category**: Operations
- **Estimated effort**: S (1 short session)
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: `PROJECT_CONTEXT.md` "Constraints" and "Team / Founder" sections contain confirmed values or an explicit reason each remains unknown.

### TASK-002 — Initialize Git repository and GitHub remote
- **Description**: Per DEC-007, `git init`, add an appropriate `.gitignore`, make the first commit of the current structure, and connect a GitHub remote.
- **Priority**: P0
- **Category**: Operations
- **Estimated effort**: S
- **Dependencies**: None
- **Status**: **Done (2026-06-29)** — see S1-01. Repo initialized, 3 commits, pushed to private `Dev555-ux/HIRA`.
- **Success criteria**: Repo is under version control, current scaffolding is committed, and the GitHub remote is set and pushed. ✅

### TASK-003 — Customer discovery interviews across candidate verticals
- **Description**: Conduct structured conversations with businesses in the six candidate verticals (DEC-006) to gather demand, willingness-to-pay, and sales-cycle signals. Validation work only — not engineering.
- **Priority**: P0
- **Category**: Validation
- **Estimated effort**: L (ongoing over the sprint)
- **Dependencies**: TASK-005 (criteria), TASK-006 (interview script) recommended first
- **Status**: To Do
- **Success criteria**: Comparable notes captured per vertical in `business/`, enough to score each on the DEC-006 criteria.

### TASK-004 — Select the first primary vertical
- **Description**: Using discovery findings, score the six verticals on market demand, willingness to pay, ease of sales, and product-market fit; choose one. Record as a new decision and update `PROJECT_CONTEXT.md` / `MEMORY.md`.
- **Priority**: P0
- **Category**: Business
- **Estimated effort**: S
- **Dependencies**: TASK-003
- **Status**: To Do
- **Success criteria**: One vertical chosen with documented rationale; DEC-006 review closed and a new "vertical selected" decision logged.

### TASK-005 — Define vertical scoring criteria
- **Description**: Make the DEC-006 criteria (demand, willingness to pay, ease of sales, PMF) concrete and measurable so verticals can be compared consistently.
- **Priority**: P1
- **Category**: Validation
- **Estimated effort**: S
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: A written scoring rubric exists in `business/`.

### TASK-006 — Build customer discovery interview script
- **Description**: Create an interview/outreach script tailored to surface the signals needed for vertical scoring.
- **Priority**: P1
- **Category**: Validation
- **Estimated effort**: S
- **Dependencies**: TASK-005
- **Status**: To Do
- **Success criteria**: Reusable script saved in `business/`.

### TASK-007 — Finalize MVP architecture
- **Description**: Decide the high-level architecture for the Assisted-Mode MVP: how WhatsApp messages flow to the AI engine, knowledge-base retrieval, Google Calendar booking/rescheduling, escalation, and conversation storage. Capture as architecture decisions and a diagram in `documentation/`.
- **Priority**: P1
- **Category**: Architecture
- **Estimated effort**: M
- **Dependencies**: TASK-008, TASK-009, TASK-010 (key technical choices feed the architecture)
- **Status**: To Do
- **Success criteria**: Architecture documented in `documentation/`, with decisions logged in `DECISIONS.md`; no open "how does X connect to Y" questions for MVP scope.

### TASK-008 — Decide WhatsApp integration path
- **Description**: Choose between the official WhatsApp Business API (direct) and a BSP/provider. Research cost, approval process, and constraints. (Open question from DEC-005.)
- **Priority**: P1
- **Category**: Research
- **Estimated effort**: M
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: A path is chosen and logged in `DECISIONS.md` with reasoning and trade-offs.

### TASK-009 — Decide AI model/provider for the conversation engine
- **Description**: Evaluate model/provider options against current pricing, context limits, capability, and latency. Per CLAUDE.md AI Engineering Principles, verify current specs rather than assuming.
- **Priority**: P1
- **Category**: Research
- **Estimated effort**: M
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: A model/provider chosen for the MVP and logged in `DECISIONS.md`.

### TASK-010 — Decide core stack and hosting
- **Description**: Choose backend language/framework, database, and hosting/infrastructure provider for the MVP, favoring boring and reliable per the technology philosophy.
- **Priority**: P1
- **Category**: Architecture
- **Estimated effort**: M
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: Stack and hosting chosen and logged in `DECISIONS.md`; reflected in `PROJECT_CONTEXT.md`.

### TASK-011 — Set up development environment
- **Description**: Establish local dev setup, project tooling/linting/formatting, and base CI once the stack is chosen. Preparation only — no feature code.
- **Priority**: P1
- **Category**: Operations
- **Estimated effort**: M
- **Dependencies**: TASK-010
- **Status**: To Do
- **Success criteria**: A new contributor can clone, install, and run lint/test scaffolding with documented steps.

---

## Next Sprint

> Begins only after a vertical is selected (TASK-004) and architecture/stack are finalized. High-priority work immediately following the current sprint. Implementation tasks will be added here once validation gates pass — intentionally not pre-populated to avoid speculative MVP scope.

_No tasks yet. To be populated after the current sprint's validation and architecture gates are met._

---

## Product Backlog

> Validated work to be completed later. Items enter only once validated; none yet.

_Empty — nothing has cleared validation yet._

---

## Research

### TASK-008 — Decide WhatsApp integration path
> Listed in Current Sprint (active). Cross-listed here as an open investigation.

### TASK-009 — Decide AI model/provider
> Listed in Current Sprint (active). Cross-listed here as an open investigation.

### RES-001 — Legal/compliance requirements
- **Description**: Research WhatsApp Business Platform policy constraints and data-privacy obligations relevant to storing customer conversations, for the likely target market(s).
- **Priority**: P1
- **Category**: Research
- **Estimated effort**: M
- **Dependencies**: Partially depends on TASK-004 (target market influences applicable law)
- **Status**: Open
- **Success criteria**: Key compliance constraints documented in `documentation/`; any that affect architecture flagged into `DECISIONS.md`.

### RES-002 — Pricing model
- **Description**: Investigate viable pricing models for the chosen vertical (per-seat, per-conversation, flat subscription, etc.).
- **Priority**: P2
- **Category**: Research
- **Estimated effort**: M
- **Dependencies**: TASK-003, TASK-004
- **Status**: Open
- **Success criteria**: A proposed pricing model documented in `business/` with supporting rationale.

---

## Technical Debt

> Known improvements intentionally postponed. None yet — no application code exists.

_Empty._

---

## Blocked

> ⚠️ Items waiting on an external dependency or an upstream decision.

- **TASK-007 (Finalize MVP architecture)** — partially blocked until TASK-008, TASK-009, and TASK-010 are decided. Can begin high-level shaping in parallel but cannot be finalized.
- **TASK-011 (Dev environment setup)** — blocked on TASK-010 (stack/hosting choice).
- **RES-002 (Pricing model)** — blocked on customer discovery (TASK-003) and vertical selection (TASK-004).

---

## Completed

> Append-only. Never remove or rewrite.

### TASK-C001 — Create `.claude/` project memory scaffolding
- **Description**: Created the `.claude/` directory and the six memory files.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: `.claude/` exists with CLAUDE.md, PROJECT_CONTEXT.md, MEMORY.md, PROGRESS.md, TODOS.md, DECISIONS.md.

### TASK-C002 — Author CLAUDE.md operating manual
- **Description**: Wrote the 17-section operating manual defining role, philosophy, standards, and workflow.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: `CLAUDE.md` populated and approved.

### TASK-C003 — Build repository structure and READMEs
- **Description**: Created 14 top-level folders, each with a README explaining purpose/contents/rationale, plus the root `README.md`.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: Folder structure and READMEs created and approved.

### TASK-C004 — Populate PROJECT_CONTEXT.md
- **Description**: Recorded current project state, MVP scope, target verticals, and explicit unknowns.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: File populated and approved.

### TASK-C005 — Populate MEMORY.md
- **Description**: Established permanent cross-session memory with all required sections.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: File populated and approved.

### TASK-C006 — Populate DECISIONS.md
- **Description**: Logged decisions DEC-001 through DEC-009.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: File populated and approved.
