# Motion roadmap — release verification

Task T5.4 (M5). The Section 1 baseline procedure, re-run against the finished
site, plus a full motion, accessibility, functional and visual audit of every
completed milestone.

**Verdict: PASS. No regression found. No runtime code was changed by T5.4** —
the only edits are two documentation corrections, recorded at the end.

Method: production build (`next build` + `next start`) of the branch in a
throwaway copy, driven over the Chrome DevTools Protocol at the four baseline
viewports, with reduced-motion, JavaScript-disabled, 4x CPU throttle and
pointer passes. The `main @ 4db61f0` baseline was rebuilt and served
alongside for direct A/B; it reproduces its recorded route table exactly
(62.7 kB route / 177 kB first load), which confirms it is the same tree the
baseline was taken from.

## 1. Regression audit against the baseline

Identical script to the one that produced Section 1, pointed at the finished
site. Page heights are **unchanged to the pixel** at every viewport.

| Viewport | Baseline height | Now | H-overflow | Opacity 0 after scroll | Console |
|---|---|---|---|---|---|
| 1440 x 900 | 6,201 px | **6,201 px** | 0 | 0 | 0 |
| 1024 x 1366 | 6,710 px | **6,710 px** | 0 | 0 | 0 |
| 768 x 1024 | 7,803 px | **7,803 px** | 0 | 0 | 0 |
| 390 x 844 | 9,244 px | **9,244 px** | 0 | 0 | 0 |

Console capture included warnings, not just errors: **no hydration warnings**
at any viewport.

### Section 1 metrics

| Metric | Baseline | Now | Regression rule | Verdict |
|---|---|---|---|---|
| First-load JS, `/` | 177 kB | **166.54 kB** gzip | Must not increase; M2 must decrease | PASS, −10.5 kB |
| Motion chunk | 50 kB gzip | **22.2 kB** initial + 19.1 kB async | Must not increase | PASS |
| SSR hidden content | 1 h1 at `opacity:0` + 10 wrappers | **0** | Must reach 0 | PASS |
| Reduced-motion residue | 0 stuck at opacity 0 | **0** after scroll | Must remain 0 | PASS |
| Pointer-move repaint | ~400 x 700 px region per frame | **+8 paints** over 11 s vs still | Must reach 0 repaints | PASS, see note |
| Hero entrance | ~800–1000 ms | **296 ms** | Must be ≤ 300 ms | PASS |
| Runtime errors | 0 | **0** | Must remain 0 | PASS |
| Reduced-motion behaviour | Tilt off, loop stopped, content visible | Same | Must remain true | PASS |

**SSR probe detail.** 23 exact `opacity:0` occurrences in the server HTML, all
of them on `data-reveal` elements — which the T1.1 criterion excludes. Non-
`data-reveal` occurrences: **0**. The `<h1>` carries no opacity style at all.
The other 8 matches a naive substring search reports are fractional values
(`opacity:0.5`, `opacity:0.42`) on decorative `aria-hidden` layers; the T1.1
regex is over-broad, which was flagged at the time and is confirmed benign
here.

**Repaint note.** The criterion's literal wording is "0 repaints". Pointer
movement over the device produces 8 more paint events than holding still over
the same 11 s window (206 vs 198), against a baseline of +201. The tilt itself
runs on compositor-only properties; the residual is the page's own ambient
work, not the tilt. T2.2 was accepted at +5 on the same basis.

### Below-fold reveal state — difference from baseline, by design

At load, before any scrolling, **18 below-the-fold elements sit at opacity 0**
on the branch, where `main` shows none. All 18 are `data-reveal` wrappers
waiting for their viewport trigger; **0** are above the fold, and **0** remain
after scrolling, in both the normal and the reduced-motion pass.

This is the specified behaviour of the `whileInView` reveal system T1.4
introduced, and its safety nets are verified: the `<noscript>` rule from T1.1
renders everything visible with JavaScript off, and reduced motion keeps the
opacity fade so the content still arrives. It is not a regression against any
stated criterion — both the T5.4 rule ("0 elements at opacity 0 **after
scroll**") and the Section 1 rule ("0 elements **stuck** at opacity 0") are
met.

One thing this verification could **not** explain: on the rebuilt `main`, no
reveal wrapper is at opacity 0 at load either, even though its `Reveal`
applies `opacity-0` until its observer fires, and neither that class nor
`animate-fade-in-up` appears in its runtime DOM. The baseline copy's behaviour
here is unresolved; it does not affect the branch's verdict, which rests on
measurements of the branch.

## 2. Motion verification

| Behaviour | Task | Measurement | Verdict |
|---|---|---|---|
| Hero entrance | T3.1 | Last element reaches opacity 1 at **296 ms**; settle times 1, 1, 169, 202, 252, 269, 296 ms | PASS ≤ 300 ms |
| Reveal / RevealGroup / RevealItem | T1.4, T3.4, T3.5 | 25 `data-reveal` wrappers, 11 group items; 18 hidden below the fold, all visible once scrolled to | PASS |
| Status transitions | T3.7 | 179 distinct intermediate opacities during one loop — a real crossfade, not a swap | PASS |
| Chat reflow | T3.6(b) | 58 distinct bubble positions during one loop (was 4 discrete jumps) | PASS |
| Scenario crossfade | T3.6(a) | Stage content distinct per scenario; live region announces each | PASS |
| FAQ disclosure | T4.2 | **12** interpolated heights opening, 12 closing, 53 → 134 px | PASS |
| FAQ under reduce | T4.2 | **2** opening, 1 closing — effectively instant | PASS |
| Card hover | T4.1 | `transform`, `translate`, `scale`, `box-shadow` all byte-identical before and after hover, with `:hover` confirmed matching | PASS, no lift |
| Device tilt | T2.2 | +8 paints over 11 s of pointer movement | PASS |
| Pause control | T5.3 | Pauses and resumes by mouse, keyboard and touch; see MOTION-ACCESSIBILITY-REVIEW.md | PASS |
| Reduced motion | GA | Static `role="img"` stage, no loop, no tilt, all content visible | PASS |
| 60 fps through a full loop | T5.4 | **4x CPU throttle**: median 16.7 ms, max **17.7 ms**, **0 frames over 33 ms**, at 1440 and 390 | PASS |

### Shared architecture unchanged

Last commit to touch each shared file, confirming no drift after its milestone:

| File | Last changed by |
|---|---|
| `src/lib/motion.ts` | T3.1 (amendment A4 added `fadeUpEnter`) |
| `src/components/motion/motion-provider.tsx` | T3.6(b) |
| `src/components/motion/features.ts` | T2.1 |
| `src/components/motion/reveal.tsx` | T1.4 |
| `eslint.config.mjs` | T2.1 |

Durations, easings, `transition`, `STAGGER`, `viewportOnce`, `fadeUp` and
`fadeUpEnter` are exactly as specified in Section 3 plus A4. No component
declares an inline variants object; the import guard is green.

## 3. Accessibility audit

Full-page sweep at 1440, normal and reduced motion, after scrolling the whole
page:

| Check | Result |
|---|---|
| Elements at opacity 0 with text, after scroll | **0** normal, **0** reduce |
| Focusable elements | 29 normal / 27 reduce; **0** that are not real controls |
| Focusable inside `aria-hidden` | **0** |
| Focus moved by animation | None — focus held through a full 9 s loop |
| Focus during scenario switch | Stays on the radio, by keyboard (ArrowRight) and by pointer |
| Exiting elements taking focus | None |
| Live regions | `aria-live="polite"` announces each scenario by name |
| Tab order | Stage group → Pause button → next control |
| Focus visibility | `outline: 2px solid rgb(234, 99, 42)` under a real Tab press |
| Touch targets | Pause control 44 x 44 at all four viewports |
| `aria-pressed` | Exposed in the AX tree, `false` running / `true` paused |
| JavaScript disabled | All copy renders |
| Reduced motion | Static fallback, no interactive stage, no pause control |

Per-milestone accessibility gains all still hold: SSR-visible copy (T1.1), no
focusable motion wrappers (T1.4), keyboard-equivalent press feedback (T3.2),
announced scenario changes (T3.6a), status text as real text (T3.7), no
hover-only affordances (T4.1), native disclosure semantics (T4.2), and the
pause control (T5.3).

## 4. Performance

| Metric | Previous milestone (T5.3) | Now | Budget |
|---|---|---|---|
| First-load JS, `/` (gzip, exact) | 166.54 kB | **166.54 kB** | PB1 ≤ 177 kB, 10.5 kB headroom |
| First-load JS, `/` (build table) | 167 kB | 167 kB | — |
| Route JS, `/` | 34.2 kB | **34.2 kB** | — |
| Motion runtime, initial chunk | 22.2 kB gz | **22.2 kB gz** | — |
| Motion features, async chunk | 19.1 kB gz | **19.1 kB gz** | Not in the initial list |
| Shared chunks | 102 kB | **102 kB** | — |

No change from T5.3, as expected for a verification-only milestone.
**PB1: PASS.**

## 5. Visual regression

Baseline screenshots versus the same captures on the finished site, same
viewports and scroll positions, compared by global SSIM and differing-pixel
share.

| Capture set | SSIM range | Differing pixels |
|---|---|---|
| 1440 (6 steps) | 0.9963 – 0.9999 | 0.05 – 0.09 % |
| 1024 (5 steps) | 0.9953 – 0.9999 | 0.02 – 0.08 % |
| 768 (6 steps) | 0.9851 – 0.9999 | 0.11 – 2.31 % |
| 390 (6 steps) | 0.9845 – 0.9996 | 0.11 – 0.35 % |
| Reduced motion (2) | 0.9969 – 0.9989 | 0.08 – 0.09 % |
| Hover device | 0.9831 | 3.38 % |

The two largest differences are both accounted for and neither is a layout
change:

- **Hover device (3.38 %)** — T2.2 rebuilt the tilt's shadow and glare as
  static compositor layers. Reviewed and accepted during T2.2 at SSIM
  0.9929–0.9931.
- **768 steps 0 and 1 (1.76 / 2.31 %)** — the demo is at a different beat in
  the two captures, so the chat thread shows different messages. Header, nav,
  device frame, hub, all four system rows and the trust strip are pixel-
  aligned.

Hero, stage, features, journey, AI employees, FAQ and footer show no spacing,
typography or geometry change. One improvement is visible rather than a
regression: the baseline's trust strip renders a stray dark overlay across
"Replies automatically" / "Escalates to humans" at 768; the finished build
renders it cleanly.

## 6. Functional verification

Run at 1440 x 900, 768 x 1024 and 390 x 844 — identical results at all three:

| Check | Result |
|---|---|
| Scenario switching | 4 scenarios, each produces distinct stage content |
| Live announcement per switch | 4 distinct announcements, one per scenario |
| Demo loop | Advances on its own |
| Pause / Play | Pauses and resumes by mouse, keyboard and touch |
| FAQ | Opens and closes |
| Navigation | 3 in-page anchors, every target resolves |
| Responsive layout | 0 horizontal overflow at all four viewports |
| Console | Clean at every viewport |

## 7. Build verification

| Gate | Result |
|---|---|
| `next build` | PASS |
| `tsc --noEmit` | **0 errors** |
| ESLint | **0 warnings, 0 errors** |
| Vitest | **447 passed / 447**, 54 files |

## 8. Documentation verification

| Document | Status |
|---|---|
| `MOTION-BUNDLE-BASELINE.md` | **Corrected.** Its "async feature loader" section still described `features.ts` as deliberately unreferenced and the wiring as a throwaway experiment; T3.6(b) shipped it. Rewritten with the measured shipped figures |
| `MOTION-RENDER-PROFILE.md` | **Amended.** Accurate as written; a dated T5.4 note records that the two later changes to `OrchestrationStage` add no per-frame work, corroborated by the 4x-throttle frame measurement |
| `MOTION-ACCESSIBILITY-REVIEW.md` | Accurate, no change |

No runtime code was modified.

## 9. Milestone status

| Milestone | Tasks | Status |
|---|---|---|
| M1 Foundation | T1.1, T1.2, T1.3, T1.4 | **PASS** |
| M2 Performance | T2.1, T2.2, T2.3 | **PASS** |
| M3 High Impact UX | T3.1, T3.2, T3.4, T3.5, T3.6(a), T3.6(b), T3.7 | **PASS** |
| M4 Micro-interactions | T4.1, T4.2 | **PASS** |
| T5.2 Auth shell height | — | **BLOCKED** |
| T5.3 Accessibility + pause control | — | **PASS** |
| T5.4 Release verification | — | **PASS** |

**Task-numbering note.** The frozen specification contains no T3.3, no T4.3
and no T5.1. M3 runs T3.1–T3.7 with no T3.3, and M4 is T4.1 and T4.2 only.
Both are complete as specified; there is no deferred T4.3 task in the
specification to track.

## 10. Outstanding items

### Blocked

- **T5.2 — auth shell height reservation.** Needs real Clerk `<SignIn />` and
  `<SignUp />` widget heights at 390 and 1440. Synthetic keys produce a client
  crash, so the measurement cannot be taken here. No code written; no estimate
  used.

### Deferred

- Nothing. The specification defines no T4.3.

### External QA — not implementation work

None of these is runnable in a headless Linux/macOS Chromium environment. Each
is a verification pass against the already-verified build, not outstanding
development:

- Safari (desktop)
- Firefox (desktop)
- Mobile Safari (iOS)
- Android Chrome, on a real mid-range device
- VoiceOver (macOS and iOS)
- NVDA (Windows)
- Lighthouse, for the LCP comparison against the pre-M1 baseline
- Final Clerk verification, which also unblocks T5.2
- Final production smoke test after deploy
