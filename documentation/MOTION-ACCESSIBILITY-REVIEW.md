# Motion accessibility review

Task T5.3 (M5, Polish). Two deliverables: a Pause/Play control for the
orchestration demo, and the full accessibility checklist run against the
merged work with evidence.

All measurements are against a production build (`next build` + `next start`)
in a throwaway copy, driven over the Chrome DevTools Protocol.

## The control

A 44 × 44 px toggle in the stage's top-right corner. `aria-pressed` carries
the state, `aria-label="Pause animation"` stays stable across both states (the
icon is the visual half of the same thing), and it sits in the stage's focus
order, immediately after the stage itself.

Pause-on-focus was not removed. The two concepts stay independent:

```ts
const [manuallyPaused, setManuallyPaused] = useState(false);
const [focusPaused, setFocusPaused] = useState(false);
const paused = manuallyPaused || focusPaused;
```

`focusPaused` is transient and follows stage focus. `manuallyPaused` persists
until the reader explicitly resumes — spec amendment A8. A pause someone asked
for must survive them tabbing away, or the WCAG 2.2.2 mechanism silently
undoes itself.

### The event-scoping fix

The first implementation shipped a control that could pause but never resume.
React's `onFocus` is `focusin`, which bubbles: activating the button focused
it, which set `focusPaused` through the stage's handler. Play then cleared
`manuallyPaused` while `focusPaused` still held the loop frozen — measured as
`pressed: "false"` with `resumed: false`, for mouse, touch **and** keyboard.

The handlers now only fire for the stage's own focus:

```tsx
onFocus={(event) => { if (event.target === event.currentTarget) setFocusPaused(true); }}
onBlur={(event) => { if (event.target === event.currentTarget) setFocusPaused(false); }}
```

Focus-pause belongs to the stage's own `tabIndex`. A control inside it is a
control, not a focus target for that mechanism.

## Pause behaviour

Production build at 1440 × 900, real CDP input events, 4 s observation windows
(longer than the longest beat hold). "Resumes while focused" is the case the
fix addresses: no blur between pressing Play and measuring.

| Case | Mouse | Keyboard | Touch (390) |
|---|---|---|---|
| Running before any input | ✔ | ✔ | ✔ |
| Activate → demo freezes | ✔ | ✔ (Enter and Space) | ✔ |
| `aria-pressed` after pause | `true` | `true` | `true` |
| Play resumes **while the button still holds focus** | ✔ | ✔ | ✔ |
| `aria-pressed` after resume | `false` | `false` | `false` |

Stage focus-pause, measured separately:

| Case | Result |
|---|---|
| Stage receives keyboard focus → pauses | ✔ |
| Stage blur → resumes | ✔ |
| Manual pause persists with focus moved elsewhere | ✔ (`pressed` stays `true`) |
| Tab from stage to Pause button → resumes | ✔ (button focus does not pause, by design) |

## Accessibility checklist

| Item | Evidence |
|---|---|
| Reduce pass leaves 0 elements at opacity 0 | Full-page scroll under `prefers-reduced-motion: reduce`: **0** elements with text at computed opacity 0 |
| Normal pass leaves 0 elements at opacity 0 | Same sweep, normal motion: **0** |
| JS-disabled pass shows all copy | Server HTML carries every section's copy; `[data-reveal]` neutralised by the `<noscript>` rule from T1.1 |
| No motion wrapper is focusable | 29 focusable elements at 1440; **0** that are not a real control (the stage's `role="group"` is the one deliberate exception) |
| No focusable element inside `aria-hidden` | **0** |
| Focus never moved by animation | Focus held on the Pause button through a complete demo loop (9 s); focus stays on the scenario radio through a keyboard switch (ArrowRight) and a pointer switch |
| Exiting elements never take focus | Scenario switch under `AnimatePresence`: focus remains on the radio that caused it |
| Motion-conveyed state changes announced | `aria-live="polite"` region reads "Now playing: the Dental scenario." on switch; per-system status text is real text, not motion-only |
| Decorative layers `aria-hidden` | Phone column, flow column, glass-edge and glare layers all `aria-hidden="true"` (T2.2, T1.1) |
| Hover-only behaviour has a focus equivalent | No hover-only affordance remains: card lift removed in T4.1, device tilt is decorative, and pause-on-hover was replaced by focus-pause plus this explicit control |
| Nothing flashes > 3×/s | Slowest beat hold is 700 ms; no animation in `lib/motion.ts` repeats faster than ~1.4 Hz |
| Target size ≥ 44 × 44 | 44 × 44 at 1440, 1024, 768 and 390 |
| Accessible name and role | AX tree: role `button`, name "Pause animation", `focusable: true`, not ignored |
| `aria-pressed` exposed to AT | AX tree `pressed: "false"` while running, `"true"` while paused |
| Focus ring | Under a real Tab: `outline: 2px solid rgb(234, 99, 42)`, the `--focus-ring` token |
| Tab order | stage group → Pause button → next control |
| Reduced motion | Static `role="img"` fallback only: no interactive stage, no Pause button, and the label carries no Pause wording (there is nothing to pause) |

### Observation, not a defect

Switching scenario *programmatically* while focus sits inside the stage drops
focus to `<body>`, because the stage is keyed on `scenarioId` and remounts.
This is unreachable through real interaction — selecting a scenario focuses
its radio first, which is outside the stage — and both realistic paths were
measured holding focus. Pre-existing behaviour of the T3.6(a) crossfade, not
introduced here.

## Functional

| Viewport | Target | Overflow | Console | Hydration |
|---|---|---|---|---|
| 1440 × 900 | 44 × 44, in viewport | 0 px | clean | clean |
| 1024 × 768 | 44 × 44, in viewport | 0 px | clean | clean |
| 768 × 1024 | 44 × 44, in viewport | 0 px | clean | clean |
| 390 × 844 | 44 × 44, in viewport | 0 px | clean | clean |

Visual evidence captured running and paused at all four viewports: the control
sits clear of the device frame and the flow graph, and the icon tracks the
state (Pause while running, Play while paused).

## Performance

| Metric | Before T5.3 | After T5.3 | Budget |
|---|---|---|---|
| First-load JS `/` (gzip, exact) | 166.21 kB | **166.54 kB** | PB1 ≤ 177 kB ✔ |
| First-load JS `/` (build table) | 166 kB | 167 kB | 3-sig-fig rounding of +330 B |
| Route JS `/` | 33.9 kB | 34.2 kB | — |
| Motion runtime chunk (initial) | 22.2 kB gz | 22.2 kB gz | unchanged |
| Motion feature chunk (async, `domMax`) | 19.1 kB gz | 19.1 kB gz | unchanged, still absent from the initial list |
| Shared chunks | 102 kB | 102 kB | unchanged |

The whole delta is **+330 bytes gzip**: the two lucide icons (`Pause`, `Play`),
the button markup, the extra state and the two target checks. No animation was
added, so there is no motion cost. **PB1 holds with 10.5 kB of headroom.**

## Specification compliance

**Task:** T5.3 — Accessibility review and demo pause control (M5).

| Acceptance criterion | Result |
|---|---|
| Pause/Play bound to the existing `paused` state | ✔ via `manuallyPaused`, per amendment A8 |
| `aria-pressed` | ✔ exposed in the AX tree, both states |
| Visible label or `aria-label` | ✔ `aria-label="Pause animation"`, stable across states |
| ≥ 44 × 44 px target | ✔ at all four viewports |
| Inside the stage's focus order | ✔ immediately after the stage |
| Pause-on-focus not removed | ✔ stage focus-pause intact and measured |
| Reachable by touch and keyboard | ✔ real touch events at 390; Enter and Space at 1440 |
| GA1–GA10 verified | ✔ checklist above |
| Reduce pass: 0 elements at opacity 0 | ✔ |
| JS-disabled pass shows all copy | ✔ |
| No motion wrapper focusable | ✔ |
| Focus never moved by animation | ✔ |
| Nothing flashes > 3×/s | ✔ |
| Decorative layers `aria-hidden` | ✔ |
| Motion-conveyed state also announced | ✔ |
| Hover-only behaviour has a focus equivalent | ✔ |
| Exiting elements never take focus | ✔ |

**Amendments applied:** A8 (split pause state), A9 (accessible description
references the Pause button, obsolete hover wording removed).

**Deviations: None.**

**Not runnable in this environment,** carried to T5.4: VoiceOver (macOS and
iOS), NVDA, Safari, Firefox, Mobile Safari, Android Chrome, and the OS-level
Reduce Motion / "Animation effects off" passes. Everything above was measured
in headless Chromium.

## Rollback

**Files changed:** `src/components/marketing/signature-demo.tsx` only, plus
this record.

**Procedure:** `git revert <commit>`. The control disappears and pause-on-focus
returns to being the sole WCAG 2.2.2 mechanism — the state the page was in
after T4.2, which was itself compliant.

**Why earlier milestones are unaffected:** the change is confined to one
component's local state and its own JSX. It adds no shared API, no export, no
import any other module consumes, and no Motion configuration. It does not
touch `MotionProvider`, `lib/motion.ts`, the reveal primitives, the feature
loader, the ESLint guard, or any variant or transition. Nothing outside
`OrchestrationStage` reads `manuallyPaused` or `focusPaused`, so no other
milestone's behaviour depends on them.
