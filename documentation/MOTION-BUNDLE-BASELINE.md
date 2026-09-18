# Motion bundle baseline

Record of `/` bundle size across the Motion roadmap (DESIGN-MOTION-001, task
T2.1). Every figure is `npm run build` in `frontend/`, reading the route table
row for `/`.

**PB1: first-load JS for `/` must stay at or below 177 kB.** From T2.1 onward
the import guard in `eslint.config.mjs` fails CI on the two ways that budget
has historically been broken: importing `framer-motion` (the legacy package
name, which would ship a second copy of the library) and importing the full
`motion` component inside `src/components/marketing/**` (which defeats the
code splitting `LazyMotion` exists for).

| Milestone | Route JS | First-load JS | Note |
|---|---|---|---|
| main @ 4db61f0 | 62.4 kB | 177 kB | Baseline. `framer-motion` 13.2, full `motion` component |
| T1.2 | 64.6 kB | 179 kB | Package swap. Over budget, permitted on an unmerged branch (amendment A2) |
| T1.3 | 51.4 kB | 166 kB | `LazyMotion` + `domAnimation`; Motion chunk 50 → 39 kB gz |
| T1.1 | 51.4 kB | 166 kB | SSR visibility fix, no bundle effect |
| T1.4 | 36.6 kB | 167 kB | Reveal primitives; Motion chunk 15 kB gz |
| T3.1 / T3.2 | 36.5 kB | 166 kB | Hero entrance, CTA wrapper removed |
| T3.4 | 36.5 kB | 166 kB | Sequence stagger, no bundle effect |
| T3.5 | 36.5 kB | 168 kB | Connector draw; +2 kB is the client boundary this adds to a server component |
| T3.6(a) | 38.3 kB | 170 kB | Scenario crossfade; +2 kB is the `AnimatePresence` import |
| **T2.1** | **38.3 kB** | **170 kB** | Guard + unreferenced loader. No change: `features.ts` is in no chunk |

## The async feature loader

`src/components/motion/features.ts` exists but is deliberately unreferenced —
verified: it appears in no emitted chunk, and `/` is byte-for-byte the same
size with and without it. It exists so layout animation can be added later
without putting `domMax` in the initial bundle.

Measured with the loader temporarily wired to `MotionProvider` (throwaway
copy, not shipped): `/` first-load fell to **166 kB** and the projection code
moved into a separate 60 kB chunk that is not in the page's initial list.
Consuming it requires resolving the module's default export:

```tsx
<LazyMotion features={() => import("@/components/motion/features").then((mod) => mod.default)} strict>
```

The `.then((mod) => mod.default)` is load-bearing: `LazyFeatureBundle` is
`() => Promise<FeatureBundle>`, so handing it the module namespace fails to
compile with "Property 'renderer' is missing".
