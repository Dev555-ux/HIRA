# Deployment — Next Steps

**This document exists because the landing page work is finished and the
deployment is not.** Nothing described here has been executed. Do not treat
any part of it as done, and do not update `MEMORY.md`'s deployment section
until someone has actually run it against real accounts.

Companion to `DEPLOYMENT.md` (the full Railway + Vercel runbook) and
`PRODUCTION_CHECKLIST.md` (what "production-ready" means beyond deployment).
This file is narrower: what specifically stands between the current `main` and
a verified live site.

---

## 1. Current status

| | |
|---|---|
| Landing page code | **Complete.** Merged to `main`, tagged. |
| Tests / typecheck / lint | **Passing.** 448 tests, clean. |
| Local verification | **Done.** 1440 / 1280 / 768 / 390, light and dark, reduced motion, keyboard. |
| Deployed | **No.** No hosting is provisioned. |
| Production verification | **Not possible.** There is no URL to verify. |

There is no Vercel project, no `vercel.json`, no `.vercel` directory and no
Vercel CLI installed. `PROJECT_CONTEXT.md` states hosting is "not yet decided
or provisioned"; `DEPLOYMENT.md` states its own steps have "not yet been
executed". Both remain accurate.

**Nothing about this release has been verified in production, because there is
no production.** Local Lighthouse numbers are measured against a local
production build and are not a substitute.

### One structural blocker specific to the landing page

`/` renders `<MarketingPage />` only for signed-out visitors with real Clerk
keys present. Locally, with no keys, `middleware.ts` redirects `/` to
`/dashboard`, so the landing page was reviewed through a throwaway
`app/preview-landing/` route that is deliberately **not committed** (it is in
`.git/info/exclude`).

The practical consequence: **the first time anyone sees this landing page at
`/` will be on the first real deployment.** That is the single highest-risk
step below, and it is why the post-deployment checklist leads with it.

---

## 2. Required accounts and secrets

Everything here needs a person with billing authority and access to real
secrets. None of it should be created by an agent.

### Accounts
| What | Why | Notes |
|---|---|---|
| **Vercel** | Next.js frontend hosting | `DEPLOYMENT.md` notes Vercel preview comments already appear on PRs — **check whether a project is already linked to `Dev555-ux/HIRA` before creating a second one.** |
| **Clerk** | Real auth. Without a publishable key the app renders `<AuthMisconfigured />` in production and the landing page never appears. | Production instance, not the dev one. |
| **Railway** (or equivalent) | API, worker, Postgres | Only needed for the app; the landing page itself is static. |
| **Domain** | `stoneveil.in` is already hardcoded as `SITE_URL` in `lib/legal.ts`, `robots.ts`, `sitemap.ts` and `metadataBase`. | If the real domain differs, those are wrong and SEO will point at the wrong origin. **Verify before first deploy.** |

### Environment variables (Vercel project)
| Variable | Notes |
|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | **Required.** Its absence is what makes `authEnabled` false and renders the misconfiguration screen. |
| `CLERK_SECRET_KEY` | Required. |
| `NEXT_PUBLIC_API_URL` | Points at the deployed API. |
| `NEXT_PUBLIC_ENABLE_EMBEDDED_SIGNUP` | Optional; gates the WhatsApp Embedded Signup entry screen. |

Cross-check against `frontend/.env.example` at deploy time — it is the
authoritative list and this table will drift.

---

## 3. Deployment checklist

1. [ ] Confirm whether a Vercel project is **already** linked to the repo.
2. [ ] Confirm the production domain. If it is not `stoneveil.in`, update
       `lib/legal.ts` `SITE_URL`, `app/robots.ts`, `app/sitemap.ts` and
       `app/layout.tsx` `metadataBase` **before** deploying — wrong values
       here get crawled.
3. [ ] Create / link the Vercel project, root directory `frontend`.
4. [ ] Set every environment variable above for Production **and** Preview.
5. [ ] Create the Clerk **production** instance; add the domain to its allowed
       origins.
6. [ ] Deploy `main`.
7. [ ] Record the deployed commit SHA from the Vercel build log.
8. [ ] Point the domain at Vercel; confirm HTTPS and certificate issuance.
9. [ ] Set `FRONTEND_URL` on the API to the real origin and redeploy it
       (CORS depends on this — see `DEPLOYMENT.md` §8).

---

## 4. Post-deployment verification checklist

Do this in a **signed-out private window**. A signed-in session redirects `/`
to `/dashboard` and you will not see the landing page at all — this is the
most likely way to wrongly conclude the deploy failed.

1. [ ] **`/` renders the landing page.** Highest risk: it has never been
       exercised outside the local preview route.
2. [ ] Deployed SHA in the Vercel log **matches `origin/main`**.
3. [ ] Hard refresh (Cmd-Shift-R). Compare against local at 1440 / 1280 /
       768 / 390 — hero, all sections, footer.
4. [ ] Dark mode via OS appearance. **Expect the two white signal bands** —
       known, see §6.
5. [ ] Hover the phone: tilt, lift, glare, graph reaction. Confirm it settles
       on mouse-out.
6. [ ] Keyboard: Tab through. Focus ring visible on every control; focusing
       the stage pauses the demo.
7. [ ] Reduced motion (System Settings → Accessibility → Display → Reduce
       motion): static resolved frame, no tilt, reflection still present.
8. [ ] **JS disabled**: confirm what renders. Expect below-fold sections to be
       blank — known, see §6. Decide whether it blocks launch.
9. [ ] DevTools console: zero errors, zero hydration warnings.
10. [ ] Lighthouse against the **live URL**, mobile and desktop. Local
        measured ~87 desktop; expect different numbers on real hardware and
        network.
11. [ ] `/robots.txt` and `/sitemap.xml` return the real production origin.
12. [ ] Open Graph: paste the URL into Slack or a card validator.

Only after 1–3 pass is it accurate to describe this as deployed.

---

## 5. Rollback checklist

The landing page is static and low-risk to revert; the risk is in the auth and
domain configuration around it.

1. [ ] **Fastest path:** Vercel dashboard → Deployments → previous good
       deployment → Promote to Production. Seconds, no git operation.
2. [ ] If the bad state is in `main`: `git revert -m 1 <merge-sha>` and push.
       Revert the merge, never force-push a shared branch.
3. [ ] The release tag stays put. Tags mark what was built; they are not
       moved to hide a bad release.
4. [ ] If rollback is caused by auth (misconfiguration screen, redirect
       loops), the cause is almost certainly environment variables or Clerk
       allowed-origins, **not** the frontend code. Check those before
       reverting anything.
5. [ ] If the domain was switched, remember `FRONTEND_URL` on the API also
       needs reverting or CORS will fail against the restored origin.

---

## 6. Known follow-up issues

Carried forward deliberately. None blocks a deploy; items 1 and 2 are the ones
worth resolving soonest.

1. **Dark-mode signal band strategy.** `Solution` and `FinalCta` use
   `bg-primary`, which inverts. In system dark mode they render as two
   near-white full-viewport slabs between dark sections. This behaves
   identically on pre-release `main`, so it is not a regression — but a
   permanently dark hero makes it far more visible, and roughly half of
   visitors browse dark. Needs a design decision on how signal bands should
   behave in dark mode.

2. **`Reveal` hides SSR content until JS runs.** Sections below the fold are
   rendered at `opacity-0` and only revealed by an IntersectionObserver. With
   JS disabled they never appear, and crawlers reading raw HTML see hidden
   text. Pre-existing and page-wide. Fix is to render visible by default and
   animate after mount.

3. **Section transition consistency.** The hero hands off to `Trust` through a
   7rem dissolve; the transitions into `Solution` and `FinalCta` are hard
   tonal edges. One soft and two hard is arguably worse than three consistent
   ones.

4. **Bundle optimisation, if profiling justifies it.** The hero interaction
   took `/` First Load JS from 165 kB to 177 kB (+12 kB) — framer-motion's
   spring/transform engine, pulled in by `useSpring`/`useTransform`/`animate`.
   Accepted deliberately. If it later matters, the obvious lever is a dynamic
   import of `DeviceShell` so it loads only on pointer-capable devices.

5. **Hero interaction on touch.** The tilt is hover-only by design — a tap
   would otherwise leave the device rotated with no way to un-rotate it.
   Touch devices currently get no equivalent. A scroll-linked variant is the
   usual answer.

6. **Materials mismatch in the hero stage.** The phone is now photographically
   detailed while the orchestration graph beside it is flat UI. They agreed
   when both were flat. Closing the gap means deciding whether the graph
   should be physical, which conflicts with keeping it visually secondary.
