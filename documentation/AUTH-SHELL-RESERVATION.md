# Auth shell height reservation

Task T5.2 (M5). Prevent layout shift when the client-rendered Clerk widget
mounts on `/sign-in` and `/sign-up`.

Measured against a real Clerk **Development** instance (Stoneveil), production
build (`next build` + `next start`), Chrome DevTools Protocol, cold load per
measurement.

## Measurements

The reserved element is the widget root Clerk mounts, `.cl-rootBox`.

| Route | 1440 x 900 | 390 x 844 |
|---|---|---|
| `/sign-in` | **488 px** | **488 px** |
| `/sign-up` | **570 px** | **588 px** |

`AuthPageShell` is shared by both routes, so each breakpoint reserves the
taller of the two — the spec's rule:

| Breakpoint | Reserved |
|---|---|
| base (< `lg`) | **588 px** |
| `lg` and up | **570 px** |

## Implementation

One line in `src/components/auth/auth-page-shell.tsx`:

```tsx
<div className="min-h-[588px] lg:min-h-[570px]">{children}</div>
```

CSS only. No JavaScript, no skeleton component, no new dependency. The wrapper
is sized rather than full-width so it remains a centred flex item and the
page's geometry is otherwise untouched.

`animate-fade-in` was **not** added: the spec calls for it only if a flash
remains after the reservation, and no layout shift or flash remains.

## Layout stability

Cumulative Layout Shift from a `PerformanceObserver` installed before
navigation, measured over the full mount.

| Case | CLS before | CLS after | Shift entries after |
|---|---|---|---|
| `/sign-in` @ 1440 | 0.00366 | **0** | 0 |
| `/sign-in` @ 390 | 0.04914 | **0** | 0 |
| `/sign-up` @ 1440 | 0.02012 | **0** | 0 |
| `/sign-up` @ 390 | **0.18571** | **0** | 0 |

The 390 sign-up case was the worst: 0.186 is above Google's 0.1 "needs
improvement" threshold. It is now zero.

Corroborating measurement at 390 — document height before the widget mounts
versus after:

| Route | Height before mount | After mount | Delta | Scroll jump |
|---|---|---|---|---|
| `/sign-in` | 844 px | 844 px | **0** | **0** |
| `/sign-up` | 844 px | 844 px | **0** | **0** |

The reservation holds the space, so nothing moves and the page never scrolls
on mount.

## Functional

| Check | Result |
|---|---|
| `/sign-in` renders the real Clerk widget | Yes — `.cl-rootBox`, 65 `cl-*` elements, "Welcome back" |
| `/sign-up` renders the real Clerk widget | Yes — 66 `cl-*` elements, "Create your account" |
| Hard navigation / refresh | Every measurement above is a cold load |
| Soft navigation (`/sign-in` → `/sign-up` via the widget link) | Route changes client-side, widget re-renders at 570 px |
| Middleware, unauthenticated → protected route | `/dashboard` redirects to `/sign-in?redirect_url=…` |
| Middleware, unauthenticated → `/` | Marketing page renders, no redirect |
| `ClerkProvider` mounts | Yes — `authEnabled === true`, widget present |
| Console | Clean, apart from the two expected development-key notices |
| Hydration warnings | **0** |
| Horizontal overflow | **0** at 390 |

**Not exercised: the signed-in `/` → `/dashboard` redirect.** It needs a real
authenticated session, which means entering credentials into the sign-in form.
That is outside what this verification can do. The unauthenticated half of the
same middleware branch is verified above.

## Accessibility

| Check | Result |
|---|---|
| Keyboard reaches the widget | Yes — Tab lands inside `cl-*` within 4 presses |
| Focus visible | `:focus-visible` matches, ring drawn via box-shadow |
| Email field labelled | "Email address" |
| Live regions | 2 (Clerk's own) |
| Shell heading | `h1` "Welcome back" / "Hire your first AI employee" |
| Reduced motion | Widget renders, reservation applied |
| JavaScript disabled | Shell still renders: heading, subheading and the link back to `/`. The widget cannot mount without JS — inherent to Clerk, unchanged by this task |

## Performance

| Metric | Before T5.2 | After T5.2 |
|---|---|---|
| `/` first-load JS (gzip, exact) | 166.54 kB | **166.54 kB** |
| `/` route JS | 34.2 kB | **34.2 kB** |
| Motion feature chunk (async) | 19.1 kB gz | **19.1 kB gz**, still not initial |
| `/sign-in`, `/sign-up` route JS | 2.14 kB | **2.14 kB** |
| **PB1 (≤ 177 kB)** | PASS | **PASS**, 10.5 kB headroom |

No JavaScript was added, so the homepage is byte-identical. The auth routes
grew by nothing measurable — the change is one Tailwind class.

## Motion verification

No Motion file was touched. `git diff` covers exactly one file,
`auth-page-shell.tsx`, which imports no Motion API. `lib/motion.ts`,
`motion-provider.tsx`, `features.ts`, `reveal.tsx` and the ESLint guard are
unchanged; shared variants, timings and transitions are untouched.

## Specification compliance

**Task:** T5.2 — Auth shell layout reservation (M5).

| Acceptance criterion | Result |
|---|---|
| Measure the mounted widget at 390 and 1440 | Done, real Clerk instance, `.cl-rootBox` |
| `min-height` on the container, larger measurement per breakpoint | 588 px base, 570 px `lg` |
| CLS for `/sign-in` and `/sign-up` is 0 | **0** in all four cases |
| No scroll jump on mount at 390 | Scroll delta **0**, document height delta **0** |
| Nothing about the auth flow itself changes | Widget, links, redirects and middleware all behave as before |
| No JS added; CSS only | One Tailwind class |
| `animate-fade-in` only if a flash remains | Not added — none remains |

**Deviations: None.**

Lighthouse was not run (not available in this environment); CLS was measured
directly from the browser's own `layout-shift` entries, which is the metric
Lighthouse reports.

## Rollback

**Files changed:** `src/components/auth/auth-page-shell.tsx` (one wrapper div),
plus this record.

**Procedure:** `git revert <commit>`. The reservation disappears and the widget
returns to shifting on mount — the state before this task.

**Why earlier milestones are unaffected:** the change is one CSS class on a
component used only by `/sign-in` and `/sign-up`. It imports no Motion API,
exports nothing new, and touches no shared module. The marketing page does not
render `AuthPageShell` at all, so no Motion milestone can observe this change —
confirmed by the homepage bundle being byte-identical before and after.
