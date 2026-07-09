# frontend/

HIRA dashboard — the business owner/staff control panel. Customers never see this (they're in WhatsApp). It layers on top of the existing authenticated backend API; it does not change any backend behavior.

## Stack

Next.js 15 (App Router) · TypeScript · Tailwind CSS v4 · shadcn-style UI (Radix primitives) · TanStack Query · React Hook Form + Zod · Clerk (auth) · next-themes (dark mode) · Lucide icons · Vitest + Testing Library.

## Getting started

```bash
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_BASE_URL; Clerk keys optional in dev
npm run dev
```

- **Auth**: with `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` set, real Clerk is used. Without it (dev only) a **mock auth** provider is used. Mock auth is **never** used in production — a production build without Clerk renders an "auth not configured" screen instead of bypassing auth.
- All API requests attach the Clerk session token (`Authorization: Bearer`).

## Scripts

- `npm run dev` — dev server
- `npm run build` — production build
- `npm run typecheck` — `tsc --noEmit`
- `npm run lint` — ESLint
- `npm run test` — Vitest

## Structure

```
src/
├── app/                     App Router
│   ├── layout.tsx           root (providers)
│   └── (dashboard)/         authenticated shell + pages
│       ├── dashboard, inbox, pending, knowledge-base, customers, leads, analytics, settings, calendar, appointments
│       ├── layout.tsx       AppShell + ErrorBoundary
│       ├── loading.tsx      route skeleton
│       └── error.tsx        route error boundary
├── components/              layout (sidebar/topbar/user-menu/mobile nav), ui/ (shadcn-style, incl. select), pending-reply-card, customer-detail, providers
├── hooks/                   TanStack Query hooks (use-pending, use-onboarding, use-knowledge-base, use-settings, use-playground, use-conversations, use-leads, use-customers, use-debounced-value, use-calendar, use-appointments)
├── lib/                     api client, auth context, config, types, utils, nav, leads (shared stage metadata), channels (multi-channel seam)
└── middleware.ts            Clerk middleware (pass-through in dev/mock)
```

## Backend integration status

Live today: **Onboarding** (`POST /api/v1/onboarding/business`), **Pending Replies** (Sprint 27, 2026-07-09 — `GET /api/v1/pending` with customer + conversation preview, editable draft via `PATCH /messages/{id}/draft`, `POST /messages/{id}/{approve,reject,regenerate,escalate}`), **Knowledge Base** (full CRUD + website import), **Playground** (AI test-drive), **Inbox** (`GET /api/v1/conversations`, `/{id}`, `/{id}/messages` — search, status filter, pagination), **Customers/CRM** (Sprint 28, 2026-07-09 — `GET /api/v1/customers`, `/{id}`, `/{id}/timeline`, full `/api/v1/leads` CRUD), **Calendar & Appointments** (Sprint 29, 2026-07-09 — `GET/PATCH /api/v1/calendar/settings`, Google OAuth connect/disconnect, `GET /api/v1/calendar/availability`, full `/api/v1/appointments` CRUD incl. reschedule/cancel), **Leads** (Sprint 32, 2026-07-10 — a Lead-first counterpart to Customers, same `GET /api/v1/leads`), **Dashboard** (Sprint 32 — real conversation/customer totals, no new endpoints), **Settings** (AI Reply Mode, with a retryable error state as of Sprint 33 — business info/WhatsApp config are not yet backed by an endpoint, and Business Information now shows real read-only data instead of a dead disabled form). Pages that need not-yet-built backend endpoints (Analytics, WhatsApp self-serve connect) render honest "coming soon" placeholder/empty states — controls with no backend are disabled rather than silently doing nothing — with typed client methods ready to connect once those endpoints exist.

### Pending Replies (`/pending`) — the AI copilot workflow

`PendingReplyCard` (`components/pending-reply-card.tsx`) turns each pending draft into: customer + conversation preview, an editable `Textarea` (dirty-state indicator, character counter against the backend's 4096-char limit), and four actions — **Approve & send** (saves an edited draft first if dirty, then approves; disabled while saving/sending or while the draft is empty), **Regenerate** (re-runs the same LLM pipeline via `POST /messages/{id}/regenerate`), **Reject**, and **Escalate**. Regenerate/Reject/Escalate all discard any unsaved edit, so if the draft is dirty they route through a `ConfirmDialog` ("Discard your edits?") instead of a browser `confirm()`. All four actions use the existing optimistic-update convention (`useApprove`'s pattern in `hooks/use-pending.ts`) and surface result/error state via the shared `useToast()`, never a dead or placeholder button.

### Customers (`/customers`) — CRM foundation (Sprint 28, 2026-07-09)

A two-pane list/detail view, matching `/inbox`'s layout convention: a searchable, paginated (`Previous`/`Next`, the app's first real pagination UI controls — `GET /api/v1/customers`'s `limit`/`offset`) customer list on the left, and a detail pane on the right (`components/customer-detail.tsx`) with three parts — the customer's profile header, an editable **Lead** card (stage/source/estimated value/notes/next follow-up date, via React Hook Form + Zod, matching the Knowledge Base entry form's convention; create/edit/delete, the last behind a `ConfirmDialog`), and a **Timeline** card merging message history with CRM (`LeadEvent`) activity, newest first, with its own `Previous`/`Next` pager. The `stage` picker is a plain native `<select>` (`components/ui/select.tsx`) rather than a Radix `Select` — `@radix-ui/react-select` isn't an installed dependency, and adding one wasn't authorized for this sprint (see DEC-031). `assigned_to` is fully supported end-to-end on the backend but has no picker in this UI yet — there's no `GET /api/v1/users` staff-list endpoint to populate one from.

### Calendar (`/calendar`) & Appointments (`/appointments`) — Google Calendar booking (Sprint 29, 2026-07-09, DEC-032)

**`/calendar`** is a connection + settings page: a status card (connect via Google OAuth redirect / disconnect behind a `ConfirmDialog` with `confirmLabel="Disconnect"`), and a timezone + working-hours form (React Hook Form + Zod, one row per weekday with an enabled checkbox and start/end time inputs, validated against IANA timezone names). The OAuth callback redirects back here with `?calendar=connected|error`, read via `useSearchParams` inside a `<Suspense>` boundary (required for Next.js App Router static generation) and surfaced as a toast. **`/appointments`** is a date-ranged list (next 30 days via `GET /api/v1/appointments`) with reschedule (`datetime-local` inputs, prefilled via `toDateTimeInputValue()`) and cancel (`ConfirmDialog` with `confirmLabel="Cancel appointment"`/`cancelLabel="Keep it"` — deliberately not the default "Delete" labels) dialogs, plus a "New appointment" dialog with debounced customer search reusing `useCustomers`/`useDebouncedValue` from Sprint 28. Both pages only exist because a real `AppointmentService`/`CalendarProvider` now backs them end-to-end (the AI orchestrator can also call `book_appointment`/`reschedule_appointment`/`cancel_appointment`/`check_availability` as tools — write actions land as `pending_approval` messages in `/pending` unless the business is in Autonomous Mode); connecting a real Google account requires the founder to supply OAuth Client ID/Secret in the backend `.env` (not done in this sprint — see DEC-032/PROGRESS.md).

### Leads (`/leads`), Dashboard totals, and the Inbox channel badge (Sprint 32, 2026-07-10, DEC-035)

An audit at the start of this sprint found Unified Inbox, Conversation Detail, and Pending Approvals already fully live from prior sprints — this sprint closed the two real gaps instead of rebuilding them. **`/leads`** is a Lead-first counterpart to `/customers`: the same two-pane layout, but the list is driven by `GET /api/v1/leads` directly (filterable by pipeline stage via chips — All + the 7 stages — or by search) rather than by customer. Selecting a lead opens the *exact same* `CustomerDetailPane` `/customers` already uses (passed the lead's `customer_id`) — there is deliberately only one lead-editing UI in the app, not two. `lib/leads.ts` is a new shared module (`LEAD_STAGES`, `STAGE_LABEL`, `STAGE_BADGE_VARIANT`) extracted from `/customers` and `components/customer-detail.tsx`, which each had their own copy of the same stage-label lookup before this sprint. **`/dashboard`**'s "Conversations" and "Customers" stat tiles now show real totals (`GET /api/v1/conversations`/`GET /api/v1/customers` with `limit=1`, reading only `meta.total`) instead of the "Coming soon" placeholders they'd shown since Sprint 28 — both endpoints already existed, they just weren't wired up. **`/inbox`** gained a `ChannelBadge` ("WhatsApp") on each conversation row and the detail header — `lib/channels.ts` is a minimal, client-side-only seam (a `Channel` type + icon/label lookup, defaulted to `"whatsapp"`) for future multi-channel support; no `channel` field exists on the backend and none was added this sprint — a channel *filter* control was deliberately not built, since with only one real channel it would be a control with nothing to filter.

### Launch Readiness & Onboarding polish (Sprint 33, 2026-07-10)

An audit before writing any code found that onboarding, empty states, loading states, and mobile responsiveness were already substantially built — `EmptyState` (with a retry action) and `Skeleton` are already used consistently across almost every data-fetching page, the app shell already has a full mobile drawer nav (`components/layout/app-shell.tsx`), and the signup form + post-signup `OnboardingChecklist` already function as a lightweight two-step wizard. This sprint closed the specific gaps the audit found rather than rebuilding any of that: **`/calendar`**'s connection and settings cards had no error state at all — a failed `useCalendarStatus`/`useCalendarSettings` query showed an indefinite loading skeleton with no explanation or retry; both now use the same `EmptyState` + retry pattern every other page already uses. **`/settings`**'s "AI Reply Mode" card had the same gap (fixed the same way), and its "Business information" card was a permanently-disabled fake form (a hover-only tooltip was the only clue it did nothing) duplicating a *working* timezone editor that already exists on `/calendar` — it now shows the real business name/industry/timezone read-only, with a "Change" link to `/calendar` for timezone instead of a second, broken control for the same setting. **`/onboarding`**'s industry picker was a hand-styled `<select>` that duplicated `components/ui/select.tsx`'s exact styling — replaced with the shared `Select` component — and submitting now shows a success toast ("You're all set!") before redirecting to `/dashboard`, instead of a silent redirect.
