# Frontend Design

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-015.
Stack: Next.js (App Router) + TypeScript + Tailwind. Auth via Clerk. This is the **business owner/staff dashboard** — the customer never sees it (they're in WhatsApp).

---

## Page Hierarchy

```
/ (marketing/login redirect)
/sign-in, /sign-up            ← Clerk
/onboarding                   ← first-run: connect WhatsApp, connect Google Calendar, seed KB
/app
 ├─ /app/dashboard            ← overview
 ├─ /app/inbox                ← conversations + Assisted-Mode approvals
 │   └─ /app/inbox/[id]       ← single conversation thread
 ├─ /app/calendar             ← appointments
 ├─ /app/knowledge-base       ← FAQ / KB management
 └─ /app/settings             ← business, integrations, mode, users
```

Shared shell: left nav (Dashboard / Inbox / Calendar / Knowledge Base / Settings), top bar (business name, user menu), with an Inbox badge for pending approvals + open escalations.

## Dashboard (`/app/dashboard`)
At-a-glance pilot metrics: conversations handled, **pending approvals**, **open escalations**, appointments booked (period). Quick links into Inbox/Calendar. Deliberately minimal for MVP — no deep analytics yet.

## Inbox (`/app/inbox`)
The core working surface in Assisted Mode.
- List pane: conversations sorted by recency; filters (All / Pending approval / Escalated / Closed); unread/pending indicators.
- Thread pane (`/[id]`): full message history; AI **drafted reply shown as pending** with **Approve / Edit & Send / Reject**; manual reply box; "escalated" banner with **Resolve**; customer info sidebar (name, number, linked appointments).

## Calendar (`/app/calendar`)
- Month/week view of `appointments`; click a slot to create; click an appointment to reschedule/cancel.
- Reflects Google Calendar state; shows connection status and re-auth prompt if the token is invalid.

## Knowledge Base (`/app/knowledge-base`)
- List of KB entries (question/title + snippet); create/edit/delete.
- Editing re-embeds on save (status indicator while embedding).
- MVP = text entries; document upload deferred.

## Settings (`/app/settings`)
- **Business**: name, vertical, timezone.
- **Mode**: Assisted ↔ Autonomous toggle (Autonomous gated/locked until that phase ships).
- **Integrations**: WhatsApp number config + status; Google Calendar connect/disconnect.
- **Users**: list staff, invite (owner only), roles.

## Conventions
- Server components for data fetching; client components for interactivity (approvals, editing).
- All data via the `/api/v1` REST API (`API.md`); JWT attached by Clerk.
- Responsive but desktop-first (business owners manage at a desk); accessible, keyboard-friendly Inbox.
- Loading/empty/error states defined per page (esp. empty Inbox, no KB entries, calendar not connected).
