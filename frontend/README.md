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
├── components/              layout (sidebar/topbar/user-menu/mobile nav), ui/ (shadcn-style), providers
├── hooks/                   TanStack Query hooks (use-pending)
├── lib/                     api client, auth context, config, types, utils, nav
└── middleware.ts            Clerk middleware (pass-through in dev/mock)
```

## Backend integration status

Live today: **Pending Replies** (`GET /api/v1/pending`, `POST /api/v1/messages/{id}/approve`). Pages that need not-yet-built backend endpoints (Inbox, Customers, Knowledge Base list, Analytics, reply Reject) render polished placeholder/empty states with typed client methods ready to connect.
