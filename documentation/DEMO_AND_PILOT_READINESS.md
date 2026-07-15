# Demo & Pilot Readiness — Sprint 43

Written **2026-07-13**. Answers one question: *if a real business owner or a
beta prospect looked at HIRA today, would they understand what it is, see it
working, and be able to actually run their business on it?* This is an audit
and a dataset design, not a plan — every claim below was verified by reading
or running the actual code, not assumed. Companion to
`documentation/PRODUCTION_CHECKLIST.md` (Sprint 34/35's audit) and
`IMPLEMENTATION_PLAN.md` (the remediation roadmap) — this doc doesn't repeat
those, it re-verifies and extends them for demo/pilot readiness specifically.

---

## Phase 1 — Demo Workspace

### What existed before this sprint

`backend/scripts/seed_demo_workspace.py` (Sprint 34) already created a
self-contained demo business ("HIRA Demo Workspace") with no WhatsApp/Calendar
connection required. Auditing it page-by-page against a fresh mock-auth
session surfaced three real gaps:

| Page | Before | Problem |
|---|---|---|
| Knowledge Base | KB facts said `"This business is HIRA Test Business, a dental and wellness clinic."` | The demo business was named "HIRA Demo Workspace" but its own knowledge base described a *different* company — an immediate tell that this is a fixture, not a real workspace |
| Inbox / Dashboard recent conversations | Every customer had exactly one inbound + one outbound message, all created in the same second | Reads as a fixture dump, not a business that's had a week of real conversations |
| Pending Replies | Exactly 1 pending reply | Looked like a fluke rather than a normal steady state |
| Appointments | Exactly 1 appointment, for the "won" customer only | The "qualified" customer (mid-funnel, consultation requested in their own conversation) had nothing on the calendar — the CRM and Calendar told two different stories |
| Leads (activity timeline) | Every lead had exactly one `LeadEvent` (`lead_created`) | The CRM's append-only timeline — a real, built feature — never actually showed more than one event, so a prospect would never see it doing anything |

### What changed

Rewrote `seed_demo_workspace.py` end-to-end (still idempotent, still safe to
re-run — see the script's own docstring for the exact idempotency contract,
which changed from "additive-only" to "reset and rebuild to spec," since this
business exists solely for this script and nothing else should hand-edit it):

- **Renamed** the business in place to **Bright Smile Dental Studio** (old
  "HIRA Demo Workspace" rows are migrated, not duplicated) and gave it its
  own dedicated knowledge base (name, address, hours, dentist, pricing,
  policies) instead of reusing `app/onboarding/knowledge.py`'s generic facts.
- **Multi-turn, backdated conversations** for all 5 customers (2–4 messages
  each, spread from 6 days ago to just now) instead of one message pair
  created in the same instant.
- **Two pending replies** (Jordan Lee, Priya Nair) instead of one.
- **Two appointments** — Sam Torres's smile-makeover consultation (qualified)
  and Alex Chen's follow-up cleaning (won) — so the calendar reflects
  exactly the customers whose conversations say they booked something, and
  no others.
- **Lead activity timelines with more than one event**: qualified/won leads
  get a `next_follow_up_at` set via `update_lead`, producing a real
  `follow_up_set` `LeadEvent` on top of `lead_created`.
- Added `backend/scripts/use_demo_business.py` — a small dev-only utility
  that repoints the mock-auth dev user's `business_id` at a named business
  (the demo workspace, or back to your own). Without this, the demo
  workspace was only inspectable via direct DB queries — mock auth always
  resolves to one fixed local user, so there was no way to actually *view*
  it in a browser. This doesn't add a product feature; it's the same kind
  of local dev tool as `seed_business.py`.

### Result

Every dashboard page now has real, coherent content when viewing Bright
Smile Dental Studio: Dashboard (KPIs, needs-attention, upcoming appointments,
recent conversations all populated), Inbox (5 conversations, mixed
statuses), Pending Replies (2), Customers (5), Leads (5, full pipeline,
multi-event timelines), Appointments (2), Knowledge Base (9 facts, own
story), Analytics (real conversation/pending totals — the "coming soon"
charts are an honest not-yet-built feature, a separate category from "no
data," left alone per this sprint's scope).

---

## Phase 1 — Demo Dataset Design

One story, one business, five customers at five different points in the
same funnel:

| Customer | Stage | Source | Value | Conversation arc | Appointment |
|---|---|---|---|---|---|
| Jordan Lee | new | WhatsApp inquiry | — | Asked about walk-ins, then teeth whitening price; latest reply drafted, awaiting approval | none yet — still deciding |
| Priya Nair | contacted | Website form | $400 | Asked about check-up + cleaning package, said she'd confirm timing; latest reply drafted, awaiting approval | none yet — still deciding |
| Sam Torres | qualified | Referral | $1,200 | Asked for a smile-makeover consultation, agreed to book | Smile makeover consultation, in 5 days |
| Alex Chen | won | WhatsApp inquiry | $250 | Thanked HIRA for a completed cleaning | Follow-up cleaning, in 3 days |
| Morgan Blake | lost | WhatsApp inquiry | — | Went with a closer clinic, declined politely | none — lost |

Design rule: **only qualified/won customers have a calendar entry.** A lead
further along the funnel has more concrete evidence of it (a booked slot);
new/contacted customers are still mid-conversation; lost customers never
convert. This is what makes the CRM and the Calendar agree with each other
instead of being two unrelated fixtures.

Knowledge base (9 facts): business name, location, hours, dentist,
appointment booking, rescheduling/cancellation, pricing, payment/insurance,
supported services — enough for the Playground to ground realistic
questions (teeth whitening price, hours, location) without inventing
anything beyond what a real dental clinic's FAQ would contain.

---

## Phase 2 — Demo Journey

One journey, using Jordan Lee's actual seeded conversation, that touches
knowledge base grounding, Assisted Mode's approval workflow, the lead
pipeline, and the dashboard — in that order, exactly as a real message would
flow through the system today:

1. **Customer messages on WhatsApp** — *(seeded as Jordan Lee's first
   inbound message, "Hi! Do you take walk-ins?")* → `POST /webhooks/whatsapp`
   persists the inbound `Message` and dispatches background processing
   (`app/webhooks/whatsapp.py` → `app/ai/processing.py`).
2. **HIRA drafts a reply, grounded in the knowledge base** — the orchestrator
   retrieves relevant KB facts (office hours, pricing) via
   `app/ai/knowledge_base.py`'s vector search and generates a reply through
   the configured LLM (Groq). In Assisted Mode (the default, and this demo
   business's mode), the reply is stored as `pending_approval`, not sent.
3. **Reply appears in Pending Replies** — *(seeded: Jordan Lee's teeth-
   whitening reply, "Teeth whitening starts at $220…", status
   `pending_approval`)* → visible on `/pending` and as the Dashboard's
   "Needs your attention" tile.
4. **Owner approves** → `POST /messages/{id}/approve` (`app/services/
   replies.py`'s `approve_and_send`) sends the WhatsApp message for real and
   marks it `sent`.
5. **Lead created or advanced** — if this is the customer's first message,
   a `Lead` is created at `stage=new` (`app/services/leads.py`'s
   `create_lead`, or the AI's own lead tool-call mid-conversation); every
   stage change appends a `LeadEvent` to the append-only timeline — this is
   what Sam Torres's and Alex Chen's seeded `follow_up_set` events
   demonstrate on `/leads`.
6. **Appointment booked** — *(seeded: Sam Torres's "let's do it" reply)* →
   either the AI proposes a calendar booking as a tool call (approved the
   same way as a text reply) or the owner books manually from
   `/appointments`; either path calls `AppointmentService.book_appointment`,
   which writes the event to Google Calendar (or the mock provider, in this
   demo) and the `Appointment` row.
7. **Calendar and CRM updated** — the appointment appears on `/appointments`
   and `/calendar`; the lead's `next_follow_up_at` and stage are visible on
   `/leads`.
8. **Dashboard updates** — KPIs (conversations, customers, pending
   approvals, upcoming appointments), "Needs your attention," and "Upcoming
   appointments" all reflect the new state on next load/refresh — no
   separate sync step, since every dashboard query reads the same tables
   this journey just wrote to.

No step above is aspirational — every one is exercised by the seeded data
and backed by code that already exists (`ARCHITECTURE.md` §7 and §14
document the same pipeline in full technical detail). What's not built yet
(a real WhatsApp/owner notification channel beyond the dashboard itself,
self-serve WhatsApp connection) is called out explicitly in Phase 4, not
implied here.

---

## Phase 3 — First-Time Experience Audit

Every empty state across the dashboard was checked against: *does it tell
the owner what to do next, not just that there's no data?*

**Already good, no change needed** (each already links to the exact next
action): Customers ("No customers yet" → Add Customer), Leads ("No leads
yet" → New Lead), Knowledge Base ("No knowledge entries yet" → Add entry),
Appointments ("No upcoming appointments" → New appointment, already wired to
the same-page dialog), Calendar (not-connected state → Connect Google
Calendar button), the onboarding checklist (`OnboardingChecklist` — every
step's status is computed from real data, "Knowledge Import"/"Test AI" link
straight to their pages, and "WhatsApp Connection"/"Go Live" are honestly
labeled "Coming soon" rather than a dead control, since no self-serve path
exists yet — see Phase 4).

**Changed this sprint** (had no next-step action at all):

- Dashboard's "No conversations yet" widget → added "Try the Playground"
  (links to `/playground`), since the honest next step while waiting for a
  real WhatsApp customer is to see the Receptionist work yourself.
- Dashboard's "No upcoming appointments" widget → added a "New appointment"
  link to `/appointments`.
- Inbox's "No conversations yet" empty state → same "Try the Playground"
  link (only when not filtering/searching).

**Deliberately left alone**: Analytics' "coming soon" chart placeholders and
Settings' "Connecting your own WhatsApp number is coming soon" — both are
honest labels for a feature that doesn't exist yet, a different category
from "empty because no data," and out of scope for a copy-only UX pass (no
new features, per this sprint's constraints).

---

## Phase 4 — Pilot Readiness Audit

### Full flow, re-walked against the running app (not just re-read)

| Area | Status | Notes |
|---|---|---|
| Authentication | **Working** | Clerk in production config; mock auth is dev-only and provably can't activate without `CLERK_JWKS_URL` unset *and* `ALLOW_MOCK_AUTH=true` (re-confirmed, `app/auth/dependencies.py`) |
| Business creation | **Working** | `/onboarding` → `POST` creates `User`+`Business`, lands on `/dashboard` with the checklist |
| WhatsApp connection | **Blocked — no self-serve path** | Same finding as Sprint 34/35, re-confirmed unchanged: connecting a business's own number is a manual backend step (`scripts/seed_business.py`-style), honestly labeled "Coming soon" in both the onboarding checklist and Settings |
| Calendar connection | **Working** | Self-serve OAuth (`/calendar`), tested end-to-end in prior sprints |
| Knowledge Base | **Working** | Add/edit/delete entries, website import, self-serve |
| Dashboard | **Working** | All four KPIs and both preview widgets are real data with retryable error states (Sprint 35) |
| CRM (Customers/Leads) | **Working** | Manual + AI-created leads, stage pipeline, append-only activity timeline |
| Appointments | **Working** | Book/reschedule/cancel, validated end-after-start, self-serve |
| Analytics | **Partially built** | Total conversations and pending approvals are real; time-series charts are an honest "coming soon", not a broken feature |

No new blocker was found in this walkthrough beyond what `PRODUCTION_CHECKLIST.md`
already tracked — but two of its previously-open findings turned out to
already be fixed in code (see below), and re-reading the actual source (not
just the plan) turned up that the other six Milestone 0 items are still
genuinely open, not just theoretically tracked.

### IMPLEMENTATION_PLAN.md Milestone 0 — re-verified against source, 2026-07-13

Updated directly in `IMPLEMENTATION_PLAN.md`'s table (not duplicated here in
full). Summary: of the 9 Milestone 0 items,

- **Already done, doc was stale**: `API-1` (reject endpoint exists,
  `POST /messages/{id}/reject`), `REL-3` (double-send race already closed —
  `approve_and_send` claims via a conditional `pending_approval -> sending`
  UPDATE before any side effect), `SEC-2` (CORS, fixed Sprint 34).
- **Still open** (verified by reading the current code, not assumed):
  - `SEC-1` — WhatsApp secrets still default to `dev-verify-token`/
    `dev-app-secret`/`dev-access-token` with no production guard.
  - `SCALE-1` — the webhook route is still `async def` doing synchronous
    DB calls directly in its body, blocking the event loop.
  - `AI-2` — KB retrieval still returns the top-k nearest entries
    regardless of similarity distance; no relevance cutoff.
  - `AI-3` — non-text WhatsApp messages (images, voice notes) are still
    silently ignored (only `type == "text"` is processed).
  - `REL-2` — an LLM generation failure still just logs and rolls back;
    no fallback message, no escalation, no Message row at all — a real
    customer would get silence with nothing on the dashboard signaling why.
  - `PERF-1` — `SessionLocal`'s `sessionmaker` still has no
    `expire_on_commit=False`.

### The actual blockers to putting one real business on HIRA today

In order of how much they'd embarrass a real pilot:

1. **No self-serve WhatsApp connection.** A founder must manually run a
   backend script per business. Fine for one white-glove pilot; not fine
   past that. Already tracked (`ONBOARD-D`/`ONBOARD-E`).
2. **`REL-2` (silent failure on generation errors)** — the one Milestone-0
   item most likely to produce a bad first impression: if the LLM call
   throws for any reason, the customer gets no reply and nothing shows up
   anywhere in the dashboard to explain why. Highest-value fix before a real
   pilot, per `IMPLEMENTATION_PLAN.md`'s own prioritization.
3. **No permanent hosting** (`INFRA-001`) — still a laptop + ngrok tunnel.
   A founder decision, not something this sprint could resolve.
4. **`SEC-1`** (insecure default secrets) — cheap to fix, should happen
   before any real webhook traffic reaches a deployed instance.
5. The remaining Milestone 0 items (`SCALE-1`, `AI-2`, `AI-3`, `PERF-1`) are
   real but lower-severity — see `IMPLEMENTATION_PLAN.md` for the full
   reasoning already captured there.

None of the above required a code change in this sprint (explicitly a
copy/dataset/UX sprint, not a remediation one) — they're re-verified and
reported here so the founder is deciding from current facts, not a
five-day-old assumption.

### Update — 2026-07-15 (Sprint 50, "Production Hardening & Release Candidate")

All six Milestone 0 items still open above (`SEC-1`, `SCALE-1`, `AI-2`,
`AI-3`, `REL-2`, `PERF-1`) are now **Done** — see `IMPLEMENTATION_PLAN.md`'s
table and `.claude/PROGRESS.md` Session 51 for the fixes and their
verification. Of "the actual blockers" list above, items 2 (`REL-2`) and 4
(`SEC-1`) are resolved. Items 1 (no self-serve WhatsApp connection) and 3
(no permanent hosting) are unchanged — both are real, both are outside
Milestone 0 (self-serve WhatsApp needs Meta business verification; hosting
is Milestone 1 / a founder infrastructure decision), and neither was in
scope for this sprint's hard rule against inventing backend functionality.
