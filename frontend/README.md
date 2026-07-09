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
│       ├── dashboard, inbox, pending, knowledge-base, customers, analytics, settings
│       ├── layout.tsx       AppShell + ErrorBoundary
│       ├── loading.tsx      route skeleton
│       └── error.tsx        route error boundary
├── components/              layout (sidebar/topbar/user-menu/mobile nav), ui/ (shadcn-style), pending-reply-card, providers
├── hooks/                   TanStack Query hooks (use-pending, use-onboarding, use-knowledge-base, use-settings, use-playground, use-conversations, use-debounced-value)
├── lib/                     api client, auth context, config, types, utils, nav
└── middleware.ts            Clerk middleware (pass-through in dev/mock)
```

## Backend integration status

Live today: **Onboarding** (`POST /api/v1/onboarding/business`), **Pending Replies** (Sprint 27, 2026-07-09 — `GET /api/v1/pending` with customer + conversation preview, editable draft via `PATCH /messages/{id}/draft`, `POST /messages/{id}/{approve,reject,regenerate,escalate}`), **Knowledge Base** (full CRUD + website import), **Playground** (AI test-drive), **Inbox** (`GET /api/v1/conversations`, `/{id}`, `/{id}/messages` — search, status filter, pagination), **Settings** (AI Reply Mode only — business info/WhatsApp config are not yet backed by an endpoint). Pages that need not-yet-built backend endpoints (Customers, Analytics, WhatsApp self-serve connect) render honest "coming soon" placeholder/empty states — controls with no backend are disabled rather than silently doing nothing — with typed client methods ready to connect once those endpoints exist.

### Pending Replies (`/pending`) — the AI copilot workflow

`PendingReplyCard` (`components/pending-reply-card.tsx`) turns each pending draft into: customer + conversation preview, an editable `Textarea` (dirty-state indicator, character counter against the backend's 4096-char limit), and four actions — **Approve & send** (saves an edited draft first if dirty, then approves; disabled while saving/sending or while the draft is empty), **Regenerate** (re-runs the same LLM pipeline via `POST /messages/{id}/regenerate`), **Reject**, and **Escalate**. Regenerate/Reject/Escalate all discard any unsaved edit, so if the draft is dirty they route through a `ConfirmDialog` ("Discard your edits?") instead of a browser `confirm()`. All four actions use the existing optimistic-update convention (`useApprove`'s pattern in `hooks/use-pending.ts`) and surface result/error state via the shared `useToast()`, never a dead or placeholder button.
