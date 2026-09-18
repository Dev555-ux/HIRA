# Marketing render profile

Task T2.3 (M2, Performance). The question T2.3 asks is narrow: **does the
orchestration demo's per-beat state update cost a frame?** The spec's rule is
to measure first and refactor only if a commit exceeds 16 ms — consolidating
the eight beat-state variables into a single `useReducer` — and to record the
measurement otherwise.

**Outcome: no code change. No commit came close to 16 ms.**

## Method

- Production build with React profiling enabled (`next build --profile`),
  served with `next start`.
- `<Profiler>` around `OrchestrationStage` and around `Hero`, plus render
  counters incrementing a ref inside each component function — the Profiler
  reports commits in a subtree, a counter reports how often the component
  function actually re-executes. Both are instrumentation in a throwaway copy;
  neither is in the shipped tree.
- Chrome DevTools Protocol at **4× CPU throttle**, one full scenario loop
  (~12–14 s), at 1440×900 and 390×844.

## Commit durations (4× CPU throttle)

| Viewport | Commits | Median | p95 | Max | Over 16 ms |
|---|---|---|---|---|---|
| 1440 × 900 | 12 | 4.5 ms | 5.9 ms | **5.9 ms** | **0** |
| 390 × 844 | 16 | 3.1 ms | 5.8 ms | **5.8 ms** | **0** |

Per component at 1440: `OrchestrationStage` max 5.3 ms / median 4.0 ms;
`Hero` max 5.4 ms / median 4.0 ms (the Hero figure is the same commits
observed at a higher boundary, not extra work).

At 4× throttle the worst commit is roughly a third of a 16.7 ms frame, so
unthrottled it is ~1.4 ms. The beat walker is not a frame cost.

## Render counts (1440 × 900)

| Scenario | `Hero` | `OrchestrationStage` | Verdict |
|---|---|---|---|
| One full loop, 12 s | **0** | 8 (one per beat) | Expected. Each beat changes what the stage shows |
| 40-frame pointer sweep | **0** | 4 | Expected. Not per-frame: the tilt runs on motion values, and these renders are the engage state change plus beats that elapsed during the sweep |
| One scenario switch | 1 | remount | Expected. `scenarioId` lives in `Hero`; the stage is keyed on it |

The two results worth stating plainly: **`Hero` does not re-render while the
demo runs or while the pointer moves**, and **40 pointer moves produce 4
renders, not 40** — the motion-value architecture from T1.3 and T2.2 is doing
what it was built to do.

## Optimisations considered and rejected

| Candidate | Why rejected |
|---|---|
| `useReducer` consolidation of the 8 beat-state variables | The trigger is a commit over 16 ms; the worst is 5.9 ms at 4× throttle. React batches the per-beat `setState` calls into one commit already, so the refactor would change structure without changing commit count |
| `memo()` on `OrchestrationStage` | Its renders are caused by its own state, which `memo` cannot prevent. The only prop is `scenarioId`, and a change there must remount it |
| `useCallback` on the beat handlers | They are not passed to memoised children, so stabilising them saves nothing |
| `memo()` on the chat bubbles | Their re-render is the point — they carry the beat's new content |

Per the project's standard, memoisation that saves no measured work is not
added: it costs readability and creates stale-closure risk for no gain.

## Remaining intentional work

8 renders per loop in `OrchestrationStage` (one per beat), 1 `Hero` render per
scenario switch, and a stage remount per switch. All are caused by state the
user or the demo actually changed, and all are well inside one frame.
