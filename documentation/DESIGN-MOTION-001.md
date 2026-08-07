# DESIGN-MOTION-001

## HIRA Premium Experience & Motion System

**Status:** Draft for review
**Type:** Addendum to `DESIGN-SCREENBOOK-001` (LOCKED)
**Depends on:** `DESIGN-SCREENBOOK-001`, `frontend/src/app/globals.css` (Sprint 46 / 65 / 68 motion work)
**Scope:** Motion, depth, micro-interaction, and premium-feel specification only.

---

### Preamble — what this document is, and is not

The Screenbook is approved and locked. This addendum **does not** touch layout, workflows, navigation, information architecture, components, or UX. It changes only how the *already-decided* surfaces move, settle, and feel.

Everything here is grounded in HIRA's existing frontend so it stays implementable without a rewrite:

- **Stack:** Next 15, React 19, Tailwind v4, Radix primitives, `lucide-react`, `next-themes`, `class-variance-authority`. No animation library.
- **Standing constraint (DEC-031 lineage):** *zero new runtime dependencies.* All motion is CSS keyframes/transitions driven by state (React mount, Radix `data-state`, or a data attribute). We do **not** introduce Framer Motion, GSAP, Lottie, or `tailwindcss-animate`.
- **Existing motion scale (Sprint 68, already in `globals.css`):** three documented tiers — *micro-interaction* (~150–200ms), *signature moment* (~700ms), *ambient/looping* (~1.5–2s). This document **extends** that scale into a full token set; it does not overwrite it.
- **Existing signature language:** "Mission Control" (`signature-settle` 700ms, `signature-pulse` 1.8s). This is HIRA's motion brand. We build outward from it rather than inventing a competing vocabulary.
- **Existing accessibility floor:** a global `prefers-reduced-motion` guard already collapses every animation to ~instant. Nothing in this document is allowed to route around it.

If any recommendation here appears to conflict with the Screenbook, the Screenbook wins and the recommendation is dropped.

---

## SECTION 1 — Motion Philosophy

### 1.1 The one sentence

> **Motion in HIRA is the visible trace of an employee doing work.**

Not transitions. Not polish. Not delight-for-its-own-sake. When something moves in HIRA, it is because *work happened* — a draft was reasoned about, a message arrived, a booking was confirmed, a system settled. Motion is the product telling the founder, truthfully, "something just happened, and here is what."

### 1.2 What "feels alive" actually means here

A founder should open HIRA and feel **"my business is running,"** not **"I'm using software."** That feeling does not come from more animation. It comes from motion that is:

- **Causal** — every movement has a cause the user can name ("the reply appeared because a customer messaged").
- **Proportionate** — routine work moves quietly; meaningful outcomes get a moment.
- **Continuous** — state changes are *shown transitioning*, never teleported, so the user never has to re-orient.
- **Calm under load** — when ten things happen at once, the interface stays composed, not frantic.

An employee who is good at their job is *calm*. HIRA's motion is calm for the same reason.

### 1.3 When things move

1. **When state changes** — a value updates, an item enters/leaves a list, a status flips.
2. **When the AI is working** — thinking, grounding, drafting, sending. (Section 6.)
3. **When work completes meaningfully** — the signature moment. (`signature-settle`.)
4. **When the user acts** — feedback on their input (button press, approve, toggle).
5. **When attention must move** — a new item in the review queue, an escalation.

### 1.4 When things *never* move

This list is as important as the one above. HIRA does **not** animate:

- **Data at rest.** A KPI that hasn't changed does not pulse, shimmer, or breathe. Stillness is the default and it signals stability.
- **Idle decoration.** No looping background gradients, no floating particles, no ambient "aliveness" with no referent.
- **The user's reading surface.** Text the user is reading (a customer message, a knowledge entry, a draft under review) does not move while they read it.
- **Anything on every render.** Refetches, polling, and re-renders must not replay animations. (This is why HIRA uses mount-triggered CSS `animation`, not transitions, for entrances — see the Sprint 46 note in `globals.css`.)
- **Navigation the user initiated deliberately.** Fast is respectful. A deliberate click gets an instant-feeling response, not a scenic transition.

### 1.5 How motion communicates the three trust signals

| Signal | How motion delivers it |
|---|---|
| **Intelligence** | Motion follows *reasoning order*, not visual order. When the AI grounds an answer, the grounding animates *before* the conclusion, so the user sees it think in sequence, not all at once. Sequence reads as reasoning; simultaneity reads as scripting. |
| **Confidence** | Timing. Confident systems don't rush and don't dawdle. Routine UI is fast (≤200ms). Meaningful outcomes get a single unhurried ~700ms beat and then *stop*. Nothing loops nervously. |
| **Trust** | Predictability and honesty. The same event always animates the same way. Motion never implies work that didn't happen (no fake "thinking" delay on a cached result), and never hides a state change (no silent swaps). |

---

## SECTION 2 — Motion Principles

Nine rules. Every animation in HIRA must be defensible against all nine.

1. **Purpose before beauty.** If you cannot state the information the motion conveys, delete the motion. Beauty is a *consequence* of purpose executed well, never the goal.
2. **Motion explains change.** The job of a transition is to make a *before* and an *after* legible as the same object moving, not two states blinking. If nothing changed, nothing moves.
3. **Motion follows hierarchy.** The most important element leads; supporting elements follow within ~80ms. Never animate a container and its children on identical timing — that reads as a slideshow, not a system.
4. **Fast UI, slow confidence.** Interaction feedback is near-instant (75–150ms). Only *earned* moments — a completed autonomous booking, a business going live — are allowed to breathe (~700ms). Never invert this.
5. **Human timing.** Nothing is truly linear except continuous ambient loops. Entrances decelerate (ease-out); the object arrives and relaxes, the way a hand placing an object does. Exits accelerate away (ease-in). This is the felt difference between "premium" and "templated."
6. **Never surprise.** No motion originates outside the user's current focus without a reason they'd predict. New review-queue items animate in *because the user knows messages arrive*; nothing else pops.
7. **Never distract.** Ambient/looping motion is rationed to at most one instance in view, low-contrast, and never adjacent to text being read.
8. **Never block work.** No animation gates input. The user can click the target before the entrance finishes; actions are cancelable; overlays are dismissible mid-animation. Motion is never a modal.
9. **Degrade to instant, always.** Every effect must remain fully functional and legible when reduced to ~0ms by the reduced-motion guard. If removing the motion breaks comprehension, the design — not the motion — is wrong.

---

## SECTION 3 — Motion Tokens

A reusable system that **extends** the existing Sprint 68 three-tier scale rather than replacing it. These are proposed as CSS custom properties added to `:root` in `globals.css`, so every surface draws from the same source and no component invents its own number.

### 3.1 Duration scale

| Token | Value | Existing tier it maps to | Use |
|---|---|---|---|
| `--motion-instant` | 0ms | — | Reduced-motion target; deliberate "no transition" |
| `--motion-ultra-fast` | 75ms | micro | Press/active feedback, cursor-proximate state |
| `--motion-fast` | 120ms | micro | Hover, focus ring, popover/menu open |
| `--motion-normal` | 180ms | micro | Standard entrance/exit, toast, sheet, list item |
| `--motion-slow` | 320ms | (new, between micro & signature) | Reveals with travel distance, panel expand, drawer |
| `--motion-signature` | 700ms | signature | One-time meaningful completion (`signature-settle`) |
| `--motion-narrative` | 1200ms | (bridges signature→ambient) | Founder delight sequences (Section 12), orchestrated multi-step reveals |
| `--motion-ambient` | 1800ms | ambient/looping | Continuous low-attention loop (`signature-pulse`) |

> Rule: a surface may only use `--motion-signature` and above for events that are genuinely rare and meaningful. Routine UI lives in `ultra-fast → normal`. This preserves the Sprint 67 audit's intent (stop inventing durations).

### 3.2 Easing curves

| Token | Value | Meaning |
|---|---|---|
| `--ease-out-quart` | `cubic-bezier(0.16, 1, 0.3, 1)` | **Primary entrance.** Already the project's house curve (used by dialog/popover/toast/sheet). Fast start, long gentle settle — the "arriving and relaxing" feel. |
| `--ease-in-quart` | `cubic-bezier(0.5, 0, 0.75, 0)` | **Primary exit.** Accelerates away. |
| `--ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` | Shared-element moves (both ends anchored). |
| `--ease-standard` | `ease-out` | Fallback for simple opacity fades (matches existing `fade-in`). |
| `--spring-settle` | (see 3.3) | Confidence spring for the signature moment and approve/confirm. |

### 3.3 Spring behavior (without a spring library)

HIRA has no physics engine and won't add one. "Spring" is expressed as a **two-stage keyframe** that overshoots slightly then settles — indistinguishable from a critically-damped spring for the small distances HIRA uses, at zero dependency cost.

- **`--spring-settle`** — a keyframe pattern: `scale(0.96) → scale(1.01) → scale(1)` over `--motion-normal`, on `--ease-out-quart`. Overshoot is capped at **1.5%** — perceptible as "life," never as "bounce." (Bounce reads as toy; HIRA is an employee.)
- Springs are reserved for **user-caused positive confirmation** (approve, save, toggle-on) and the signature settle. Never on exits, never on error, never on ambient loops.

### 3.4 Semantic motion tokens

Map intent to primitives so components reference *meaning*, not numbers:

| Semantic token | Composition |
|---|---|
| `motion/entrance` | `--motion-normal` · `--ease-out-quart` · fade+4px rise (existing `fade-in-up`) |
| `motion/exit` | `--motion-fast` · `--ease-in-quart` · fade+2px |
| `motion/hover` | `--motion-fast` · `--ease-standard` |
| `motion/focus` | `--motion-fast` · `--ease-out-quart` (ring expands, never blinks) |
| `motion/press` | `--motion-ultra-fast` · scale 0.98 |
| `motion/success` | `--spring-settle` + one brightness breath (from `signature-settle`) |
| `motion/failure` | `--motion-fast` · **positional shake ≤3px, 2 cycles, no color flash** (see 5.x) |
| `motion/shared` | `--motion-slow` · `--ease-in-out` (element persists across views) |
| `motion/interrupt` | `--motion-ultra-fast` cancel of any in-flight motion → jump to end state |

### 3.5 Shared-element transitions

React 19 + Next 15 give View Transitions API access without a library. Where the *same object* persists between two states (a queue card → its expanded review view; a customer row → customer detail), HIRA uses a shared-element move (`motion/shared`) rather than cross-fade, so the object's identity is never lost. **Feature-detected and progressively enhanced:** where the View Transitions API is unavailable, it falls back to `motion/entrance`/`motion/exit`, never breaking.

### 3.6 Interruption model

- Any new motion on an element **cancels** the in-flight one and eases from the *current* computed value (never snaps to start). CSS transitions do this natively; keyframe animations get a `motion/interrupt` override class.
- User input always wins. A click during an entrance completes the entrance instantly and processes the click.

### 3.7 Reduced motion (token-level)

The global guard stays authoritative. At the token level, reduced-motion maps **every** duration token to `--motion-instant` **except** it preserves *opacity* fades at a clamped 80ms (a pure cross-fade carries no vestibular risk and preserves change-legibility for low-vision users). Transforms, travel, scale, and loops all go to 0. This is a refinement of, not a replacement for, the existing `@media (prefers-reduced-motion: reduce)` block.

---

## SECTION 4 — Visual Depth

Premium depth **without changing a single layout.** Everything below is surface treatment applied to the *existing* boxes: it changes shadow, light, and material, never position or size.

### 4.1 The lighting model

HIRA has one, consistent, implied light source: **soft, slightly cool, from above and marginally front-left.** Every shadow in the product must be consistent with this one light. Inconsistent shadow direction is the single most common tell of amateur UI; HIRA never varies it.

- **Light mode:** shadows are cool-grey and low-opacity, never pure black.
- **Dark mode:** we do **not** use dark shadows (they vanish on `hsl(240 10% 4%)`). Depth in dark mode comes from **surface lightness** — the existing token ladder already does this: `background 4%` → `card 6%` → `popover 6%` → `accent 16%`. Elevation = a lighter surface + a hairline top highlight (a 1px inset border at ~8% white on the top edge only), simulating light catching the raised edge.

### 4.2 Elevation ladder

Six elevation levels, each a *fixed* pairing of surface + shadow so nothing is ad-hoc:

| Level | Surface | Light-mode shadow | Dark-mode treatment |
|---|---|---|---|
| **E0 — canvas** | `--background` | none | none |
| **E1 — card** | `--card` | `0 1px 2px rgba(cool, .04)` + hairline border | `--card` + hairline border |
| **E2 — raised card / hover** | `--card` | `0 2px 8px rgba(cool,.06)` | E1 + top-edge highlight |
| **E3 — popover / menu / select** | `--popover` | `0 8px 24px rgba(cool,.10)` | `--popover` + top-edge highlight, stronger |
| **E4 — dialog** | `--popover` | `0 16px 48px rgba(cool,.16)` + backdrop | + backdrop |
| **E5 — command palette** | `--popover` | `0 24px 64px rgba(cool,.22)` + backdrop blur | brightest surface + heaviest highlight |

Shadows are always **soft and offset downward** (consistent with the light source), never hard, never symmetric, never colored (except the focus ring, §4.6).

### 4.3 Ambient light & materials

- **Ambient occlusion, faked cheaply:** where a raised surface meets the canvas, a 1px border at slightly higher contrast than the fill gives a grounded edge. HIRA already sets `border-color: var(--border)` globally — this is the material seam and should stay visible.
- **Material = matte, not glass.** HIRA's surfaces are *paper-like*: opaque, matte, quietly textured by shadow. We explicitly **reject** glassmorphism as a system-wide material (per the brief). **One** exception, used sparingly: the **command palette** and **dialog backdrops** may use a *subtle* backdrop blur (8–16px) purely to push the underlying UI out of focus and pull attention forward — this is *depth-of-field*, not decoration, and it degrades to a plain dim overlay where `backdrop-filter` is unsupported or under reduced-transparency settings.
- **Gradients:** allowed only as **near-invisible tonal shifts** (≤3% lightness across a surface) to give large flat areas a sense of light falloff. Never as brand color washes, never with visible bands, never animated.

### 4.4 Surface hierarchy for AI

HIRA needs one visual concept the Screenbook establishes and motion reinforces: **the AI surface is distinct from the user surface.** Anything authored/handled by the AI (a draft, a reasoning trace, an autonomous action log) sits on a subtly differentiated material:

- A **faint left border or spine** in a low-saturation "intelligence" tone (derived from foreground, not a new brand color) marks AI-authored content.
- AI surfaces get **E1 elevation with a marginally warmer/cooler tint** (≤2% from `--card`) so they read as "handled for you" without shouting.
- This is the *only* place HIRA uses tint to encode meaning, and it is deliberately near-threshold. (Confirm exact treatment against the Screenbook; if the Screenbook already specifies AI-surface styling, defer to it — this section adds only the *depth/light* behavior, not new color.)

### 4.5 Blur (rationed)

Blur exists in exactly three places: (1) dialog/palette backdrops (depth-of-field, §4.3); (2) the leading/trailing edge of a horizontally scrolling row as a scroll affordance (a soft mask, not animated); (3) skeleton-to-content handoff, optional. Nowhere else.

### 4.6 Focus rings

Focus is the one place HIRA uses a **colored, animated** treatment — because focus is critical for keyboard users and must be unmissable:

- Ring uses `--ring`, offset 2px, at `motion/focus` timing — it **grows** into place (scale of the ring box from 0.9→1 + opacity), never blinks or pulses.
- Focus ring is **always visible on keyboard focus** (`:focus-visible`), never suppressed. On pointer interaction it is suppressed per platform convention.
- The ring is a first-class object with its own elevation feel — it sits *above* the element's own shadow.

### 4.7 Component depth summary

| Component | Rest | Hover | Active/Focus |
|---|---|---|---|
| **Card** | E1 | E2 (lift, `motion/hover`) | ring |
| **Button (primary)** | E1, filled `--primary` | slight brightness ↑, E1→E2 | press: scale 0.98 (`motion/press`), then `--spring-settle` on release |
| **Button (ghost/secondary)** | E0 | `--accent` fill fades in | ring |
| **Dialog** | E4 + backdrop | — | trapped focus ring |
| **Panel / sheet** | E1 seam | — | — |
| **Popover / dropdown / select** | E3 | item: `--accent` | roving ring |

---

## SECTION 5 — Micro-Interactions

Every interactive element, fully specified. All timings reference Section 3 tokens. All are subject to the reduced-motion guard.

### 5.1 Buttons

- **Hover:** background/brightness shift over `motion/hover`. Ghost buttons fade in `--accent`. No movement (buttons don't rise on hover — cards do; keeps a hierarchy between "surface" and "control").
- **Press (pointer down):** `scale(0.98)` over `--motion-ultra-fast`. Immediate — this is the single most important "feel" moment; latency here reads as a laggy product.
- **Release / success:** `--spring-settle` back to 1.0. For a *committing* action (Approve, Save, Send) the release also fires `motion/success` (one brightness breath).
- **Loading:** label cross-fades to a **determinate-feeling** inline spinner (a rotating quarter-arc, `--motion-ambient` linear). Button width **does not change** (reserve the label width) — no layout shift. Button becomes `aria-busy`, non-interactive, but not visually "greyed to death."
- **Disabled:** reduced opacity, no motion, `cursor: not-allowed`. Never animates.
- **Destructive:** identical mechanics, but no spring on release (destruction is not celebrated) and confirmation is required via `ConfirmDialog`.

### 5.2 Cards

- **Hover:** E1→E2 lift over `motion/hover` (2px shadow growth + ≤1px `translateY(-1px)`). The lift is *tiny* — presence, not a jump.
- **Press (if clickable):** settle back toward E1 (pressing *into* the surface), inverse of hover.
- **Enter (list mount):** `motion/entrance` (`fade-in-up`), staggered (§5.3).
- **Exit (removed from list):** collapse height + fade over `motion/exit`; siblings reflow on `--motion-normal` so the gap closes smoothly, never snaps.

### 5.3 Lists & stagger

- New items enter with `motion/entrance`, **staggered by 30ms** per item, **capped at 6 items** of stagger (beyond that, remaining items share the last delay) — so a list of 50 doesn't cascade for 1.5s.
- Stagger only applies on **first paint / meaningful insert**, never on refetch/reorder (mount-triggered animation guarantees this, per the Sprint 46 note).
- Reordering uses shared-element/FLIP-style position transitions (`motion/shared`) so an item that moves is *tracked*, not blinked.

### 5.4 Sidebar / navigation (`sidebar-nav.tsx`, `topbar.tsx`, `app-shell.tsx`)

- **Active item indicator** is a shared element: a single pill/left-bar that **slides** from the old active item to the new one over `--motion-slow` · `--ease-in-out`. One indicator that moves — never one that fades out here and in there.
- **Hover** on nav items: `--accent` fills over `motion/hover`.
- **Mobile drawer** (existing raw-Radix left sheet): keep the existing `sheet-left-show/hide`. Add a synchronized backdrop fade and a **1px content-follow** (content behind the drawer shifts ≤4px and dims) to reinforce the sheet sitting *above* the page.
- **Collapse/expand** (if present): width animates on `--motion-slow`; labels cross-fade slightly *behind* the width change (labels fade at 60% of the width duration) so text never appears to stretch.

### 5.5 Search & Command Palette

The command palette is HIRA's flagship micro-interaction — it should feel like the fastest, most certain surface in the product.

- **Open:** backdrop dims + depth-of-field blur (§4.3) over `--motion-fast`; the palette itself enters E5 with `motion/entrance` scaled from 0.98 and rising 4px. Total open ≤160ms. Input is focused *before* the animation completes (never wait for motion to accept typing).
- **Query → results:** results list is **stable-keyed**; matching items reorder via `motion/shared`, non-matches fade (`motion/exit`). The list must **never fully unmount+remount on each keystroke** (that flickers) — it filters in place.
- **Highlighted result:** a single roving highlight bar that **slides** between rows on arrow-key nav (`--motion-fast`), matching the sidebar's "one indicator that moves" law.
- **Match highlighting:** matched substrings get weight/underline change, applied instantly (no per-character animation — that's a gimmick).
- **Execute:** palette exits `motion/exit` *immediately* on selection (don't make the user watch it leave); the resulting action's own motion takes over.
- **Empty/no-results:** copy cross-fades in over `motion/entrance`; never a jarring layout jump.

### 5.6 Inputs & textareas (`input.tsx`, `textarea.tsx`)

- **Focus:** ring grows (`motion/focus`); border shifts `--input`→`--ring` on the same timing. No label bounce.
- **Label (if floating):** moves on `--motion-fast` · `--ease-out-quart`; travels as a shared element, doesn't fade-swap.
- **Validation error:** border→`--destructive` over `motion/exit` timing; the message enters below via height+fade (`motion/entrance`), pushing siblings smoothly. **No shake on inputs** (reserve shake for action-level failure, §5.11). Errors are stated, not shouted.
- **Character count (e.g. draft `MAX_DRAFT_LENGTH`):** counter color transitions to `--warning` then `--destructive` as limits approach, over `motion/hover` — a calm gradient, no blink.
- **Autosave:** see §5.10.

### 5.7 Checkboxes

- **Check:** the checkmark **draws** (stroke-dashoffset) over `--motion-fast` · `--ease-out-quart`; box fill scales in behind it with a micro `--spring-settle`. The draw makes it feel *deliberate*, like a hand ticking a box.
- **Uncheck:** instant fill removal + `motion/exit` on the mark (undoing isn't celebrated).
- **Indeterminate→checked:** bar cross-fades to checkmark.
- **Onboarding checklist items** (`onboarding-checklist.tsx`): completing an item = check draw + the row's status badge lands on "Done" via the existing `fade-in`; a subtly bigger moment than a normal checkbox because it's progress toward going live (see §12).

### 5.8 Switches / toggles

- **Thumb:** slides on `--motion-fast` · `--ease-out-quart` with a **trailing** feel (thumb leads, track color fills to meet it) — track color transition lags the thumb by ~40ms so the thumb appears to *carry* the state.
- **On:** micro `--spring-settle` on the thumb as it lands. **Autonomous-mode toggles** (turning an AI Employee autonomous) get an elevated treatment — see §6.9, this is a trust moment.
- **Off:** thumb slides back, no spring, track desaturates. Off should feel like a calm, reversible step-down, never an alarm.

### 5.9 Dialogs (`dialog.tsx`, `confirm-dialog.tsx`)

- Keep existing `dialog-content-show/hide` + `overlay-show/hide` — they already use the house curve and Radix Presence.
- **Refinement:** the backdrop should *lead* the content by ~30ms on open (world dims, then dialog arrives) and *trail* on close (dialog leaves, then world returns) — this ordering reads as the dialog being *summoned from* and *returning to* depth.
- **ConfirmDialog for destructive actions:** the confirm button carries no spring; the dialog's entrance is the same calm curve (we don't make destruction feel urgent or exciting — calm confirmation reduces error).
- **Focus** moves to the dialog's primary affordance on open, returns to the trigger on close (§10, focus restoration).

### 5.10 Loading & saving

HIRA distinguishes three loading textures — using the wrong one is a premium-feel failure:

1. **Skeletons** (`skeleton.tsx`) — for *structural* first loads (a page/list arriving). A slow shimmer (`--motion-ambient`, low-contrast) indicating "content is coming." Skeletons match the final layout's shape exactly so the content-swap causes **zero layout shift**. Skeleton→content is a cross-fade over `motion/entrance`, not a snap.
2. **Inline spinners** — for a *specific action* the user triggered (button loading, §5.1). Small, local, determinate-feeling.
3. **Optimistic updates** — for *user edits* (approve, edit draft, toggle). The UI reflects the intended end-state **immediately**, with a quiet "saving" affordance; on failure it reverts with an explanation (§5.11). This is the highest-trust texture and HIRA's default for review-queue actions where the backend contract allows it.

- **Saving indicator** (autosave, settings): a small text state — `Saving…` → `Saved` with a check that draws — cross-fading on `motion/hover`. Never a blocking spinner for background saves.

### 5.11 Deleting & failure

- **Delete:** item collapses + fades (`motion/exit`), gap closes (`--motion-normal`). Where reversible, an **Undo** toast enters — the deletion is *optimistic*, and the item can spring back into place (`motion/entrance`) if undone.
- **Failure:** the **failed control** (not the whole page) does a **positional shake** — `≤3px, 2 cycles, ~200ms total, no color strobe**. This is the *only* shake in HIRA. It says "that didn't go through" in body language, not alarm. Accompanied by a toast stating what happened and what to do. Under reduced motion the shake is replaced by an instant border→`--destructive` + the toast.
- Failure never uses red flashing, never uses sound by default, never blocks the rest of the UI.

### 5.12 Notifications / toasts (`toast.tsx`)

- Keep existing `toast-show/hide` (slide-in from right, height-collapse on exit). Refinements:
- **Stacking:** multiple toasts stack with a 30ms stagger; older toasts recede (scale 0.98, opacity 0.85) so the newest is clearly foremost — a small depth stack, not a wall.
- **Auto-dismiss:** a **hairline progress line** along the bottom edge depletes over the toast's lifetime (linear) so dwell time is honest and predictable. Hovering pauses depletion (§10).
- **Severity:** success/info are calm; only true failures use `--destructive` and they **do not auto-dismiss** (require acknowledgement).

### 5.13 The Review surface (pending/escalations queue — `pending-reply-card.tsx`)

This is where HIRA's promise is felt, so it gets Section 9's full narrative treatment. Micro-interaction summary for the card's controls:

- **Approve** → `motion/success` + optimistic send; card completes and leaves via `motion/exit`; queue closes the gap.
- **Reject / Escalate / Regenerate** → confirm via `ConfirmDialog` (edits at risk), then optimistic transition; Regenerate morphs the draft in place (§9).
- **Edit** → textarea focuses with `motion/focus`; character counter live (§5.6); the AI-surface spine (§4.4) subtly recedes while the *human* is editing (ownership handoff made visible).

---

## SECTION 6 — AI Motion Language

This is HIRA's differentiator and the heart of "it feels like I hired someone." We design a small, coherent visual grammar for AI states so the user reads the AI as a **capable colleague at work**, not a chatbot performing.

### 6.0 Design rules for the AI language

- **One motif, many states.** All AI states are variations of a single visual primitive (below), so the AI always feels like *one* entity, differently occupied — not a soundboard of unrelated effects.
- **No anthropomorphic clichés.** No "typing dots" as the primary metaphor, no sparkle/star "magic AI" iconography, no glowing orbs, no pulsing brains. HIRA's AI reads as *competent staff*, and competent staff don't sparkle.
- **Honesty.** An AI motion state must correspond to real backend work. No decorative "thinking" on instant results. Duration reflects actual latency; if work is fast, the state barely appears — which is itself reassuring.

### 6.1 The core primitive — "the working line"

HIRA already owns a signature: the **travelling pulse along a cable** (`signature-pulse`, work moving through the business). We elevate that same idea into the AI's body language. The AI's presence is a **line/edge that carries motion when work is flowing and rests flat when idle.** Every state below is a modulation of this one line — its speed, direction, segmentation, and brightness — plus a state label. White/foreground-toned only, no glow, consistent with the existing `signature-pulse`.

### 6.2 State grammar

| State | Line behavior | Label / affordance | Feel |
|---|---|---|---|
| **Idle** | Flat, still, at rest (no motion) | none / "Ready" | A colleague at their desk, available |
| **Thinking** | Slow, short segment travelling, unhurried (`--motion-ambient`) | "Thinking…" | Considering, not rushing |
| **Reasoning** | Segment travels then **branches/steps** — visibly sequential beats | reasoning steps reveal one-by-one (§6.3) | Following a chain of thought |
| **Grounding** | Line briefly **reaches toward** the knowledge source, returns carrying it | "Checking knowledge base" + source chip lands | Fetching what it knows before answering |
| **Searching knowledge** | Faster segmented travel scanning across | result count ticks up | Actively looking things up |
| **Booking appointment** | Line travels to the calendar surface, a slot **fills** | "Booking…" → slot solidifies | Doing a concrete task |
| **Sending message** | Line travels *outward* off the card edge (toward the customer) | draft lifts and departs (§9) | Handing work off / dispatching |
| **Escalating** | Line **redirects upward** toward the human, hands off | "Escalated to you" + item routes to queue | Knowing its limits, deferring to you |
| **Waiting** | Line paused mid-path, dimmed, holding | "Waiting on customer" / "Waiting on you" | Blocked, patiently, not stuck |
| **Learning** | New segment **joins** the line and integrates (a knowledge entry lands) | "Learned from this" | Getting better, permanently |
| **Autonomous mode** | Line flows **continuously** and self-completes actions without a stop | subtle persistent flow (see §6.9) | The employee working on its own |
| **Assisted mode** | Line flows to a **stop** at the review gate, waits for you | draft rests in review (§9) | Drafting *for your approval* |

### 6.3 Reasoning must be sequential

When a reasoning trace expands (e.g. `trace-detail.tsx`), its steps **reveal in order** with `motion/entrance` staggered (§5.3), *even if all data is already available*, because **sequence is what reads as thought.** A batch-appearing trace reads as a data dump; a stepping trace reads as reasoning. Cap total reveal at ~600ms regardless of step count (stagger compresses for long traces). Steps the user has seen before do not re-animate on re-expand.

### 6.4 Grounding is shown *before* the conclusion

The single most trust-building AI motion: when a draft is grounded in knowledge, the **source chip lands first**, then the conclusion resolves. Seeing the evidence arrive before the answer is what separates "the AI looked it up" from "the AI made it up." This ordering is mandatory wherever grounding exists.

### 6.5 Thinking that respects real latency

- If backend work returns in <150ms, **skip the thinking animation** — snap to the result. A fake delay to "show intelligence" is dishonest and, worse, makes the product feel *slower*.
- If work takes 150ms–2s, show "Thinking" (line motion) with no time pressure.
- If work exceeds ~2s, the line adds a **quiet progress texture** and, past ~5s, a plain-language status ("Still working — checking your calendar"). Never a raw spinner, never a percentage that lies.

### 6.6 Sending & escalation are *directional*

Direction encodes meaning: **outward** (off the card, toward the world) = sending to a customer; **upward** (toward the top-bar/human) = escalating to the founder. Consistent directionality means the founder learns to read HIRA's intent peripherally, without labels.

### 6.7 Learning is permanent and visible

When the AI learns (a new knowledge entry created from an interaction), a segment **joins and integrates** into the line and the knowledge count increments with a `--spring-settle` on the number. This is one of HIRA's most valuable feelings — *the employee is compounding* — and it recurs at the 100-entries delight moment (§12).

### 6.8 Idle is a feature, not an absence

An idle AI is **completely still.** Stillness communicates *stability and availability* — the employee is there, not busy, nothing wrong. Resist any urge to add ambient "aliveness" to idle AI; a fidgeting idle state reads as anxious or broken. HIRA's confidence is partly expressed by how comfortable it is being still.

### 6.9 Autonomous vs Assisted — the trust dial

The difference between these two modes is the product's core trust proposition, so motion must make the mode **legible at a glance**:

- **Assisted:** the working line always **flows to a stop at the review gate.** Every draft comes to rest and *waits for you*. The recurring "arriving and pausing" motion is the felt promise "nothing goes out without you."
- **Autonomous:** the line **flows through** — actions self-complete with a brief `signature-settle` on each completed action, then rest. The felt promise is "it's handling this."
- **Switching Assisted→Autonomous** (a switch, §5.8) is a genuine trust moment: the review gate visibly **opens** (the stop point dissolves) over `--motion-slow`, a one-time confirmation states what just changed ("Maya can now reply on her own"), and it is always instantly reversible. This is deliberately a *considered* moment, not a casual flip — motion gives it appropriate weight without alarm.

---

## SECTION 7 — Landing Page Motion

Motion redesign **only** — layout, sections, and copy are locked by the Screenbook. Existing components: `hero.tsx`, `signature-demo.tsx`, `ai-employees.tsx`, `how-it-works.tsx`, `solution.tsx`, `problem.tsx`, `features.tsx`, `trust.tsx`, `faq.tsx`, `final-cta.tsx`, `site-header.tsx`, `site-footer.tsx`.

**Governing idea:** the landing page should feel like *watching an AI employee work*, not like a marketing site performing tricks. The existing "Mission Control" signature demo is the centerpiece and everything else defers to it.

### 7.1 Page entrance

- Above-the-fold enters as **one composed breath**, not a cascade: headline, subhead, primary CTA rise together via `fade-in-up` with a *tight* 40ms stagger (leader → support → CTA), completing in ≤300ms. Fast, confident, done. No hero that animates for 2 seconds while the user waits.
- The site header settles in place (no slide); it's the frame, it should feel already-present.

### 7.2 Hero sequence

- The hero's supporting visual (the working-line / Mission-Control motif) begins its ambient flow *after* the text has settled, so the reading path is text-first.
- **No parallax** on the hero (per brief). Depth comes from the elevation system (§4), not scroll-coupled movement.

### 7.3 Signature demo reveal (`signature-demo.tsx`)

- Keep the existing **Mission Control** behavior verbatim: independent systems doing work, then the **synchronized `signature-settle`** (one boolean flip → genuinely simultaneous brightness breath) and the `signature-pulse` travelling cables. This is the brand; do not replace it.
- **Motion refinement only:** trigger the demo's *entrance* (and, if not already, its looping activity) via `IntersectionObserver` when it scrolls into view — it should be *at rest* until seen, then come alive, so a founder scrolling down catches the business "starting to run" exactly as they arrive. Pauses when scrolled away (performance + honesty).

### 7.4 Employee cards (`ai-employees.tsx`)

- Cards enter on scroll-into-view with `motion/entrance`, staggered (§5.3), capped.
- **Hover:** the card lifts (E1→E2, §5.2) and its employee's working-line does *one* quiet pass — a preview of that employee "doing their job." Only the hovered card animates; the rest stay still.
- Cards do **not** all idle-animate simultaneously (that's a particle wall); at most the one under the pointer is active.

### 7.5 Scroll transitions

- Section content enters via `IntersectionObserver` + `motion/entrance`, **once** (never re-animating on scroll-up — re-triggering reads as cheap).
- Entrances are subtle rises + fades only. **No** pinned/scroll-jacked sequences, no horizontal scroll hijack, no scroll-scrubbed video. The user's scroll always maps 1:1 to the page. Respect momentum (§10).

### 7.6 How-it-works / features / trust

- `how-it-works.tsx` may reveal steps **sequentially on scroll** (matching §6.3's "sequence reads as reasoning") — as the user scrolls, each step's working-line completes, so the *page itself* demonstrates the product working through a task.
- `trust.tsx` (logos/proof): fade in, no motion after. Trust marks that jitter undermine trust.

### 7.7 Pricing

- Cards enter staggered. **Plan toggle** (monthly/annual, if present) slides a shared indicator (§5.4 law) and prices **roll** (digit transition over `--motion-fast`) rather than blink — a small, satisfying, honest number change. Recommended plan's subtle emphasis is static, not a looping pulse.

### 7.8 CTA interactions (`final-cta.tsx`, primary buttons)

- Primary CTA uses the full button spec (§5.1) with `--spring-settle` on release. On the final CTA, hover does *one* working-line pass beneath the button — the last thing the visitor sees before converting is a glimpse of the employee ready to start.
- No pulsing/breathing CTAs (looping attention-grabs read as desperate; HIRA is confident).

### 7.9 Footer (`site-footer.tsx`)

- Enters on scroll like any section. Link hovers use `motion/hover`. The footer is calm and final — no ambient motion, a quiet close to the page.

---

## SECTION 8 — Dashboard Motion (`app/(dashboard)/dashboard/page.tsx`, `dashboard-hero.tsx`, `stat-card.tsx`)

**Governing idea:** opening the dashboard should feel like walking into an office where work is already underway — not like booting a program.

### 8.1 Opening the dashboard

- The shell (sidebar, top-bar) is **already present** — it does not animate on every navigation (that would punish frequent use). Only the *content region* transitions.
- Content arrives as skeletons matching final layout (§5.10) → cross-fades to real data. The hero greets first, KPIs and panels follow with a tight, capped stagger. Total to "settled" ≤400ms on warm load.

### 8.2 Loading

- Skeletons only for true first-load. Subsequent visits (cached) should feel **instant** — show cached data immediately, quietly reconcile deltas (§8.4). Never re-skeleton data you already have.

### 8.3 Review queue preview

- The dashboard's view into the pending queue: items present statically if already loaded. A **newly arrived** item (customer just messaged) enters via `motion/entrance` **with the working-line** (§6) so the founder sees *the AI has already drafted a reply* — the arrival *is* the reassurance. A small count badge increments with `--spring-settle`.

### 8.4 KPI updates (`stat-card.tsx`)

- A KPI value that **changes** does a **digit roll** (odometer-style) over `--motion-fast`, or a cross-fade for non-numeric — so change is *witnessed*, not silently swapped. A value that *hasn't* changed **does not move** (§1.4).
- Direction/sentiment: an improving metric's delta indicator settles with a micro up-move; a worsening one settles with a down-move — quiet, no color strobe.
- First paint: value replaces its skeleton via `fade-in` (existing), not a count-up-from-zero (count-ups are a gimmick and misrepresent the number mid-animation).

### 8.5 Employee status

- Each AI Employee shows its current state via the §6 grammar (idle/thinking/working/waiting). Status *changes* animate the line; steady states are still. The founder should be able to glance at the dashboard and read "who's working on what" from body language alone.

### 8.6 Recent activity

- An append-only feed. New entries enter at the top via `motion/entrance`; existing entries slide down on `--motion-normal` to make room (never a hard jump). Capped stagger. The feed is *calm* — activity flows in at reading pace, it does not spray.

### 8.7 Knowledge updates

- When knowledge grows, the count increments with `--spring-settle` and, if visible, the new entry lands with the §6.7 "learning" integration. This ties the dashboard to the compounding-employee feeling and to the 100-entries delight moment (§12).

### 8.8 Calendar updates (`calendar/page.tsx`, `appointments/page.tsx`)

- A **newly booked** slot (especially an AI-booked one) **fills in** via the §6 "booking" motion — the slot solidifies rather than appearing. AI-booked vs human-booked are distinguishable via the AI-surface treatment (§4.4). Existing appointments are static; only the *new* one animates.

---

## SECTION 9 — Inbox Motion (`app/(dashboard)/inbox/page.tsx`, `pending-reply-card.tsx`, `escalations/page.tsx`)

**Governing idea:** every message in the inbox should tell a small story — *a customer asked → the employee understood → it drafted a reply → it's waiting for you (or it handled it).* Motion narrates that story so the founder trusts what happened without reading every word.

### 9.1 Customer message arrives

- The inbound message enters via `motion/entrance` on the *customer* (user) surface — plain, human, no AI treatment. A subtle unread affordance settles in. This is the *stimulus*; the AI's response is the story.

### 9.2 Draft appears

- Immediately after (or, if pre-computed, on open) the AI's **working line** runs briefly (§6.1) and the **draft resolves** onto the AI surface (§4.4) below/beside the message. The draft *builds* — grounding chips land first (§6.4), then the reply text resolves — so the founder watches it reason, not just output. Under reduced motion, the draft simply appears complete with grounding chips present.

### 9.3 Reasoning expands

- The reasoning/trace is collapsed by default (calm). Expanding it reveals steps **sequentially** (§6.3). Collapsing is instant. The reasoning surface is clearly AI-material and clearly secondary to the draft.

### 9.4 ReviewBar enters

- When a draft needs the founder, the **review controls** (Approve / Edit / Reject / Escalate / Regenerate — `pending-reply-card.tsx`) enter via `motion/entrance` and **come to rest** — the Assisted-mode "flow to a stop at the gate" (§6.9). The bar's arrival-and-stillness is the felt promise: *nothing sends without you.* The primary (Approve) affordance is the natural focus target.

### 9.5 Approve

- `motion/success` (spring + one brightness breath) on Approve → the draft **lifts and departs outward** (§6.6, sending direction) → the card completes and leaves via `motion/exit` → the queue closes the gap (`--motion-normal`) → the **next** item settles up into focus. Optimistic (§5.10): the send is reflected instantly; failure reverts with a shake (§5.11) and explanation. The whole approve→next flow should feel like *clearing your desk*, one confident motion at a time.

### 9.6 Reject / Edit

- **Reject:** `ConfirmDialog` if edits exist → card resolves to a rejected state and leaves via `motion/exit`; no celebration.
- **Edit:** textarea focuses (`motion/focus`), the AI-surface spine **recedes** as the human takes authorship (§5.13), live character count (§5.6). Saving the edit re-asserts the draft; Regenerate warns first (edits at risk, per existing `CONFIRM_COPY`).

### 9.7 Autonomous reply

- In Autonomous mode, the draft does **not** stop at a gate — the working line **flows through**, the reply **departs outward** on its own with a brief `signature-settle` marking completion, and the item moves to a "handled" state. The founder sees it happen (transparency) but isn't asked to act. Reviewing after the fact is always available. This visible self-completion is what makes autonomy *feel* trustworthy rather than opaque.

### 9.8 Escalation

- The working line **redirects upward** (§6.6) and the item **routes** (shared-element move, `motion/shared`) from the inbox toward the escalations surface / top-bar, with a one-line reason. The founder should feel the employee *deferring to them appropriately* — "I wasn't sure, so I brought this to you" — which paradoxically increases trust in autonomy.

### 9.9 Typing / composing indicators

- Where a live "AI is drafting" state exists, it uses the **working line**, never three bouncing dots (§6.0). The line's motion *is* the "composing" signal, keeping the AI as one coherent entity rather than borrowing chat-app clichés.

---

## SECTION 10 — Premium Details (the 100)

The small things that, in aggregate, separate premium software from competent software. Grouped for reference; each is individually actionable and individually subject to the reduced-motion guard.

**Cursor & pointer**
1. `cursor: pointer` on every genuinely clickable element, `default` on non-interactive — audited, no exceptions.
2. `cursor: text` over editable regions, including the whole textarea padding box, not just the text.
3. `cursor: not-allowed` on disabled controls (paired with `aria-disabled`).
4. `cursor: grab`/`grabbing` on any draggable (e.g. reorder handles) — state changes on pointer-down.
5. `cursor: col-resize` on resizable panel seams.
6. Custom cursor only where it adds meaning; never a decorative custom cursor.
7. Loading actions show `cursor: wait` only when truly blocking; optimistic actions keep the normal cursor.

**Selection & text**
8. Text selection color derives from `--accent`, tuned for legible contrast in both themes.
9. Non-selectable UI chrome (button labels, nav) uses `user-select: none` so double-clicks don't select UI.
10. Content the user *should* be able to copy (customer message, IDs) is fully selectable.
11. Double-click selects a word, triple-click a paragraph, in editable drafts — native, preserved.
12. Copyable IDs/values show a copy affordance on hover and confirm with a check that draws (§5.7).

**Keyboard navigation**
13. Every interactive element reachable by Tab in visual order.
14. `:focus-visible` ring on keyboard focus, suppressed on pointer (§4.6).
15. Command palette on `Cmd/Ctrl-K` from anywhere.
16. `Esc` closes the topmost overlay only (never nukes the whole stack).
17. Arrow keys rove within menus/lists/palette; Home/End jump.
18. `Enter` activates the focused primary action; `Cmd/Ctrl-Enter` submits from within a textarea (approve/send a draft without reaching for the mouse).
19. Roving `tabindex` in toolbars/menus so Tab doesn't trap the user inside a widget.
20. Visible, discoverable shortcut hints (`⌘K`, `⌘↵`) rendered as `kbd` chips, styled, not raw text.
21. Type-ahead in long selects/lists.
22. Skip-to-content link for keyboard/screen-reader users at the top of the tab order.

**Focus & state restoration**
23. Closing a dialog/menu returns focus to the trigger.
24. Navigating back restores scroll position.
25. Navigating back restores focus to the element you left from where feasible.
26. Draft edits survive an accidental navigation (warn or preserve), never silently lost.
27. Filter/sort/search state persists across navigation within a session.
28. Command palette remembers recent commands and surfaces them first.
29. Expanded/collapsed states (reasoning traces, sections) persist per session.

**Hover, delay & intent**
30. Tooltips have an open **delay** (~400ms) and a shorter close delay — no flicker on pass-through.
31. Adjacent tooltips share a "warm" state — once one has opened, neighbors open with no delay until the user rests.
32. Submenus use a **safe-triangle** hover path so diagonal travel to the submenu doesn't dismiss it.
33. Hover effects have a tiny out-delay so brushing past doesn't strobe.
34. Destructive actions never trigger on hover — click/confirm only.

**Loading, skeletons & perceived speed**
35. Skeletons match final layout exactly → zero layout shift on content arrival.
36. Cached data shows instantly; deltas reconcile quietly (§8.2).
37. Button width is reserved during loading (no reflow, §5.1).
38. Images/avatars reserve their box (aspect-ratio) so text doesn't jump when they load.
39. Optimistic UI for user edits wherever the backend contract allows (§5.10).
40. Prefetch likely-next routes on link hover/focus (Next.js) so navigation feels instant.
41. A minimum spinner display time (~300ms) prevents a "flash" of spinner on near-instant loads.

**Scrolling & overscroll**
42. Momentum/inertial scroll preserved (never override native scroll physics).
43. `overscroll-behavior: contain` on inner scroll areas so scrolling a list doesn't bounce the page.
44. Sticky headers within scroll regions settle with a hairline shadow only once content scrolls beneath them.
45. Scroll position of inner panels persists when the panel re-renders.
46. Horizontal-scroll rows show soft edge masks (§4.5) as an affordance, and are keyboard/trackpad scrollable.
47. `scroll-margin` on anchor targets so linked content isn't hidden under sticky headers.
48. No scroll-jacking anywhere; scroll maps 1:1 to the page (§7.5).
49. Long lists virtualize where needed, but preserve scroll-restoration and focus.

**Empty, zero & error states**
50. Every list has a designed empty state (`empty-state.tsx`), not a blank void — with a single clear next action.
51. First-run empty states are *aspirational* ("your first customer will appear here"), not apologetic.
52. Error states state what happened + what to do, never a raw stack/status code to the founder.
53. Error boundaries (`error-boundary.tsx`) fail gracefully to a recoverable surface, never a white screen.
54. A slow-network state ("still working…") after ~5s (§6.5), never an infinite silent spinner.
55. Offline/degraded state is communicated calmly with retained last-known data.

**Transitions & continuity**
56. Route changes transition only the content region, not the shell (§8.1).
57. Shared elements (row → detail) move rather than cross-fade (§3.5).
58. List reorders use FLIP-style position transitions (§5.3).
59. One moving indicator per navigation group (sidebar, tabs, palette) — never fade-out-here/fade-in-there (§5.4).
60. Height changes (accordion, expanding cards) animate smoothly, siblings reflow, never snap.

**Typography refinement**
61. Tabular/lining numerals (`font-variant-numeric: tabular-nums`) on all KPIs, counts, and money so digits don't jitter as they change.
62. Proper typographic quotes, dashes, and ellipses in product copy.
63. Consistent, sensible line-length (~60–75ch) for reading surfaces (messages, knowledge entries).
64. `text-wrap: balance` on headings; `text-wrap: pretty` on paragraphs to avoid orphans.
65. Optical alignment: punctuation/icons hang so text edges look aligned.
66. Consistent numeric/date/relative-time formatting (`formatRelativeTime` already in use) product-wide.
67. Truncation with ellipsis + accessible full value on hover/focus, never a hard clip.
68. No text reflow/jump when a value updates (reserve space, use tabular numerals).

**Spacing & alignment**
69. A single spacing scale, adhered to — no one-off `13px`.
70. Optical centering of glyphs/icons inside buttons (icons rarely center mathematically).
71. Consistent icon size and stroke weight (`lucide-react`, one stroke width system-wide).
72. Hairline borders at true 1px on all densities (no blurred sub-pixel lines on HiDPI).
73. Consistent corner radii from `--radius` and its derived scale; nested radii concentric.

**Color, theme & material**
74. Instant, flash-free theme switch (`next-themes`), including on first paint (no white flash in dark mode — SSR theme cookie).
75. Both light and dark fully designed for every new surface (never dark-as-afterthought).
76. Elevation via surface lightness in dark mode, not black shadows (§4.1).
77. One consistent implied light source for every shadow (§4.1).
78. Focus ring visible and adequate-contrast in both themes.
79. Never encode meaning by color alone (pair with icon/shape/text) — colorblind-safe.
80. Disabled states legible, not invisible.

**Buttons, controls & feel**
81. Press-scale on primary buttons (§5.1) — the core "feel" moment.
82. Spring-settle on positive commits, none on destructive/exit (§3.3).
83. Generous hit targets (≥44px effective) even where the visual is smaller.
84. Loading buttons keep their width and stay `aria-busy` (§5.1).
85. Toggles carry state with the thumb leading and track trailing (§5.8).
86. Checkmarks draw rather than pop (§5.7).

**Notifications & feedback**
87. Toasts stack with depth and an honest depletion line (§5.12).
88. Hovering a toast pauses its auto-dismiss.
89. Undo offered for reversible destructive actions (§5.11).
90. Success confirmations are quiet; only failures are insistent (and require acknowledgement).
91. No duplicate/queued spam toasts — coalesce repeats.

**AI-specific polish**
92. AI "thinking" is skipped entirely on sub-150ms results (§6.5) — honesty *and* speed.
93. Grounding evidence lands before the conclusion, every time (§6.4).
94. Idle AI is perfectly still (§6.8).
95. AI-authored content always carries the AI-surface treatment so authorship is never ambiguous (§4.4).
96. Directional consistency: outward = to customer, upward = to you (§6.6).

**System hygiene**
97. Reduced-motion honored globally, with opacity fades preserved (§3.7).
98. No animation replays on refetch/re-render (mount-triggered only, per Sprint 46 note).
99. All motion pauses when its surface is offscreen (`IntersectionObserver`) or the tab is hidden (`visibilitychange`) — battery and honesty.
100. Nothing loops without a reason and a reduced-motion off-switch; at most one ambient loop in view at a time.

---

## SECTION 11 — Sound (Optional)

Sound is **off by default**, opt-in, and the product must be *complete and premium in total silence.* Sound is a garnish for the few earned moments, never a feedback channel the UI depends on.

### 11.1 Principles

- **Silent-perfect first.** If any information is only available via sound, the design is broken. Sound only ever *accompanies* a visual state.
- **Rare and earned.** Sound maps to the same events as `--motion-signature`/delight (§12), not to routine clicks. A product that beeps on every action is a toy.
- **Physical, not synthetic.** Where used, sounds are soft, short (<300ms), organic (a felt/wood/paper texture), low-frequency-warm — the sonic equivalent of HIRA's matte material. No sci-fi blips, no "AI" chimes, no notification-app dings.
- **Respect the room.** Default off. Respects OS "silent"/reduced-audio and the tab's mute. Never plays on page load. Ducks/steps aside for anything else playing.

### 11.2 Candidate moments (all optional, all opt-in)

| Moment | Sound |
|---|---|
| Approve & send | A soft, single, satisfying "settle" — the desk-clearing feel (§9.5), paired with `motion/success`. |
| Autonomous action completed | The faintest confirmation tick — reassurance the employee did something while you were away. |
| First customer / first booking (§12) | A warmer, slightly fuller one-time tone — a genuine milestone. |
| Business goes autonomous (§12) | The most resonant of the set, once, memorable. |
| Error requiring acknowledgement | A low, soft, non-alarming tone — "look here," not "alarm." Never harsh. |

### 11.3 Controls

- A single global "Interface sounds" toggle in settings, default **off**, with a one-line audition.
- Volume is fixed-modest; no per-sound configuration (that's a synth, not a product).

---

## SECTION 12 — Founder Delight Moments

Rare, earned, emotional. Each is a **one-time** `--motion-narrative`/`--motion-signature` moment the founder remembers — the emotional glue that turns a tool into "someone I hired." These reuse the existing `signature-settle` vocabulary so delight feels like *the same brand*, amplified, not a different app.

**Design rules for all delight moments:**
- **Once.** Fires on the genuine first occurrence, never repeats, never re-triggers on refetch (persist a flag). A milestone that recurs is not a milestone.
- **Non-blocking, skippable.** Always dismissible; never gates work; the underlying action already succeeded before the celebration plays.
- **Named, specific, personal.** Uses the founder's real data ("Maya just booked your first appointment"), not generic confetti.
- **Restrained.** Elevated, not loud — the brief bans particle explosions and sparkle clichés. Delight in HIRA is *warmth and weight*, not fireworks.
- **Reduced-motion & silent variants** for every one.

| Moment | The feeling | Motion (all one-time) |
|---|---|---|
| **First customer** | "It's real." | The inbound message lands with a slightly fuller entrance; a quiet, personal one-liner settles in ("Your first customer just reached out"). |
| **First booking** | "It actually *did the job*." | The calendar slot fills via the §6 booking motion, then a single `signature-settle` across the appointment; named ("Maya booked Priya for Tuesday 3pm"). |
| **AI's first autonomous booking** | "It worked *without me*." | The working line flows through end-to-end unassisted, self-completes, and settles — the founder *watches* autonomy succeed once, deliberately. The single most trust-defining moment; give it a beat. |
| **100th conversation** | "This is compounding." | A quiet count landmark with `--spring-settle` on the number; a one-line reflection on what's been handled. |
| **Knowledge reaches 100 entries** | "My employee got smarter." | The §6.7 "learning" integration, amplified once — segments visibly joining the line; the knowledge count settles at 100 with weight. Ties directly to the compounding-employee theme. |
| **Business goes autonomous** | "I hired someone, and now they're running it." | The peak moment. The review gate dissolves (§6.9), the working line transitions to continuous self-completing flow, and a single resonant, personal statement settles — the culmination of everything above. The one place HIRA is allowed its fullest expression (still restrained, still matte, still no confetti). Optional sound (§11.2). |

**Placement discipline:** delight moments live *at the point of the event* (the inbox, the calendar, the dashboard), not in a separate "achievements" surface — the celebration is part of the work, which is what makes it feel real rather than gamified.

---

## SECTION 13 — Accessibility

Accessibility is a **gate, not a section** — every item in Sections 1–12 is already written to pass it. This section states the non-negotiable floor.

### 13.1 `prefers-reduced-motion`

- The existing global guard in `globals.css` is authoritative and stays. Every new token, keyframe, and effect in this document routes through it.
- Refinement (§3.7): under reduced motion, *transforms/travel/scale/loops → 0*; *opacity cross-fades → clamped 80ms* (safe, and preserves change-legibility). No effect may bypass the guard with `!important` or JS-driven animation.
- **Every** delight moment, AI state, and signature moment has a defined reduced-motion form that still conveys the same information (state still changes, evidence still lands, milestone text still appears — just without travel).

### 13.2 Keyboard users

- Full keyboard operability for every flow (§10, items 13–29). No mouse-only path exists.
- Focus is always visible (`:focus-visible`), never trapped except intentionally within modals (with `Esc` to exit), always restored on close.
- Motion never steals or blocks focus; input is never gated on an animation finishing (§2.8).

### 13.3 Screen readers

- Motion is decorative to the accessibility tree; **state** is announced via semantics, not animation. AI states use `aria-live="polite"` regions ("Thinking", "Drafted a reply", "Escalated to you") so a non-visual user gets the same narrative the working-line gives a sighted user.
- Loading uses `aria-busy`; toasts use appropriate `role="status"`/`role="alert"` (failures assertive, successes polite).
- Purely decorative motion elements are `aria-hidden`.
- Live-updating values (KPIs) announce changes politely without spamming.

### 13.4 Low power / reduced data / older hardware

- All motion pauses offscreen and on hidden tabs (§10.99) — this is a performance *and* battery guarantee.
- Effects are GPU-cheap by construction: **transform and opacity only** (never animate layout properties — width/height/top/left — except deliberately-cheap height accordions with `content-visibility` care). This keeps everything on the compositor and off the main thread.
- No continuous animation runs when nothing is happening (§6.8 idle stillness doubles as a power feature).
- Respects `prefers-reduced-transparency` (drops backdrop blur to a plain dim, §4.3) and `prefers-reduced-data` (skips non-essential ambient loops).
- Target: nothing in this system should drop frames on modest/older hardware, because none of it is doing expensive work — that's a design constraint, not an optimization pass.

### 13.5 Vestibular safety

- No large-travel motion, no parallax, no spin, no zoom-through, no autoplaying scaling backgrounds. HIRA's motion is small by design (≤4px travel for entrances, ≤1.5% scale overshoot), which is inherently vestibular-safe even before the reduced-motion guard.

---

## SECTION 14 — Implementation Plan

Six reviewable PRs, sequenced so each lands value independently and later PRs build only on merged tokens. Every PR ships behind the existing zero-dependency, CSS-first approach — no animation library is introduced at any stage.

**Global "Definition of Done" (applies to every PR below):**
- All motion draws from Section 3 tokens; no ad-hoc durations/curves introduced.
- Reduced-motion path verified (transforms→0, opacity fades preserved).
- Keyboard + screen-reader path verified for any interactive change.
- Transform/opacity only; no layout-property animation; offscreen/hidden-tab pause where looping.
- No animation replays on refetch/re-render (mount- or state-triggered only).
- Both themes verified. No new runtime dependency. No Screenbook layout/UX change.

---

### PR1 — Motion Tokens & Primitives (foundation)

**Scope:** Add the Section 3 token set (durations, easings, spring keyframe, semantic tokens) to `globals.css` alongside the existing Sprint 68 scale; add the §3.7 reduced-motion refinement; document usage. No component behavior changes yet — this is the shared vocabulary.
- **Risk:** Low. Additive; existing animations keep working. Main risk is duplicating/contradicting existing tokens — mitigate by mapping every new token to an existing tier explicitly (done in §3.1).
- **Performance impact:** None (definitions only).
- **Accessibility:** Establishes the refined reduced-motion contract everything else depends on. Must be verified here.
- **Rollback:** Trivial — revert the CSS additions; nothing references them yet.
- **DoD:** Tokens documented and available; existing dialog/popover/toast/sheet/signature animations re-expressed in terms of tokens with zero visual change (verified side-by-side); reduced-motion refinement verified.

### PR2 — Micro-Interactions (Sections 4 & 5)

**Scope:** Depth/elevation system (§4) applied to existing `card`, `button`, `dialog`, `popover`, `select`, `input`, `textarea`, focus rings; button press/spring, card lift, checkbox draw, switch thumb, list stagger, toast stacking/depletion, loading textures. Surface-level only; no layout change.
- **Risk:** Medium — touches every shared UI primitive, so regressions are broad. Mitigate with the existing component tests (`button.test.tsx`, `stat-card.test.tsx`, etc.) and visual review per component.
- **Performance impact:** Negligible (transform/opacity, GPU-composited). Watch stagger caps on long lists.
- **Accessibility:** Focus ring behavior, `aria-busy` on loading, reduced-motion on every effect. `:focus-visible` audit.
- **Rollback:** Per-component; each primitive's motion is independently revertible.
- **DoD:** Every primitive in §5 matches spec in both themes; no layout shift introduced; all existing tests pass; reduced-motion verified per component.

### PR3 — Landing Page Motion (Section 7)

**Scope:** Motion-only refinement of marketing components; `IntersectionObserver` scroll entrances (once), employee-card hover working-line, signature-demo in-view trigger/pause, CTA feel, footer. Reuses PR1/PR2. **No layout/copy change.**
- **Risk:** Low–medium. Self-contained to `marketing/*`; main risk is scroll-entrance jank or re-trigger — mitigate with "animate once" flags and offscreen pause.
- **Performance impact:** Low; observers are cheap and effects pause offscreen. Verify no long-running loops when hero is scrolled away.
- **Accessibility:** Reduced-motion collapses entrances to instant-visible (content never hidden behind an animation that won't play); keyboard/scroll unaffected.
- **Rollback:** Revert `marketing/*` motion; page renders static, fully functional.
- **DoD:** Landing "feels like watching an employee work"; Mission Control demo unchanged in behavior, now in-view triggered; no scroll-jank; reduced-motion static version verified.

### PR4 — Dashboard Motion (Section 8)

**Scope:** Shell-stable route transitions, skeleton→content handoff, KPI digit-roll (`stat-card.tsx`), review-queue arrival with working-line, employee status via §6 grammar, activity feed, knowledge/calendar updates. Depends on PR1/PR2 and introduces the first working-line usage (coordinate with PR5's AI grammar — see note).
- **Risk:** Medium — real data + optimistic/reconcile paths; risk of animating on refetch. Mitigate strictly with mount/state-triggered animation and the "unchanged values don't move" rule; cover with `dashboard-hero.test.tsx`/`stat-card.test.tsx`.
- **Performance impact:** Low. Ensure KPI rolls use tabular numerals + transform/opacity; no layout shift.
- **Accessibility:** `aria-live` for status changes; KPI changes announced politely; skeleton `aria-busy`.
- **Rollback:** Per-widget; dashboard degrades to static values.
- **DoD:** Opening the dashboard "feels like walking into a running office"; no animation on refetch (verified by forcing refetch); reduced-motion + screen-reader narration verified.

### PR5 — Inbox & AI Motion Language (Sections 6 & 9)

**Scope:** The working-line primitive and full §6 state grammar; inbox narrative (message arrive → draft build → grounding-first → reasoning sequential → ReviewBar rest → approve/reject/edit/escalate/autonomous) in `inbox/page.tsx`, `pending-reply-card.tsx`, `escalations/page.tsx`, `trace-detail.tsx`. The product's signature experience.
- **Risk:** **High** — most novel, most behaviorally intertwined with real backend states, highest trust stakes. Mitigate: land the working-line primitive first (small, testable in isolation), then wire states incrementally behind the existing queue tests (`inbox/page.test.tsx`, `escalations/page.test.tsx`); honesty rules (skip <150ms, grounding-before-conclusion) verified against real latencies.
- **Performance impact:** Low per instance (single line, transform/opacity), but **cap concurrent working-lines** and pause offscreen — an inbox of 50 must not run 50 loops.
- **Accessibility:** Every AI state has an `aria-live` announcement equivalent; reduced-motion shows completed states with grounding present, no travel. This is where a11y parity matters most.
- **Rollback:** Feature-flag the working-line/AI states; falling back shows drafts/controls statically (fully functional, just not narrated).
- **DoD:** Inbox "tells the story" for every state in §9; grounding-before-conclusion and skip-on-fast-result verified; Autonomous vs Assisted legible at a glance; reduced-motion and screen-reader narratives verified; concurrency cap verified.

### PR6 — Polish, Delight & Sound (Sections 10, 11, 12)

**Scope:** The Section 10 hundred-detail audit (cursor/selection/keyboard/focus-restoration/scroll/typography/empty-states sweep), the Section 12 delight moments (one-time, flagged, personal), and the optional opt-in sound layer (§11).
- **Risk:** Low individually, but broad surface area. Mitigate by treating §10 as a checklist audit (each item a small independent change) and gating delight moments behind persisted first-occurrence flags with explicit tests for "fires once, never on refetch."
- **Performance impact:** Negligible; delight moments are one-time; sound is opt-in and lazy-loaded.
- **Accessibility:** Every delight moment has reduced-motion + silent + screen-reader-announced variants; sound is off-by-default and never an information channel; the §10 sweep is itself largely accessibility hardening.
- **Rollback:** Highly granular — each detail and each delight moment is independently revertible; sound layer removable wholesale via one flag.
- **DoD:** §10 checklist fully audited and passing in both themes; each delight moment fires exactly once with personal data and has verified reduced-motion/silent/SR variants; sound perfect-when-muted and off by default.

---

## FINAL OBJECTIVE — the measure

Every decision in this document is answerable to one test:

> When a founder uses HIRA, they should say:
> **"This doesn't feel like software. It feels like I hired someone."**

The motion system delivers that not by adding animation, but by making every movement the honest, calm, proportionate trace of an employee doing real work — grounded in the vocabulary HIRA already owns (the working line, the signature settle), never noisy, never flashy, never gimmicky, and fully functional in perfect silence and perfect stillness for anyone who needs it that way.

**The Screenbook remains locked and unmodified. This addendum specifies motion, depth, and feel only.**

*End of DESIGN-MOTION-001.*
