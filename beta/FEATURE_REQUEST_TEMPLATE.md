# Feature Request Template

Copy this block for every feature request. The point of this template is to force the *problem* to be stated before the *solution* — testers (and founders) naturally jump straight to "you should add X," which skips the one question that actually determines whether X is worth building.

```
Requested Feature:
  What they're asking for, in their own words — the solution as they
  imagine it, not yet the underlying problem.

Why User Wants It (the actual problem):
  What are they actually trying to do? Describe the situation, not the
  feature above. ("I can't tell which leads haven't been followed up on in
  3+ days" — not "add a follow-up reminder feature.") This is the durable
  part; the requested feature is one data point on how they think about it,
  not a spec.

  Current workaround: what do you do today instead? ("Nothing, I just
  forget" is a valid and important answer — it means the pain is real but
  not painful enough to have built a habit around yet.)

Business Value:
  What happens if this never gets built? Lost time, lost revenue, lost
  customers, or just mild annoyance? Be honest here even if it makes the
  request look less urgent — an inflated value rating is what leads to
  building the wrong thing next.

Frequency Requested:
  Daily / Weekly / Occasionally / Once (happened once, might not recur) —
  and how many separate testers have independently asked for this. One
  person asking is a data point; three independently asking is a pattern.

Estimated Complexity:
  Trivial / Small / Medium / Large — a rough gut call for triage purposes,
  not a real estimate. This is what separates "good idea, do it this week"
  from "good idea, needs real scoping before it's queued anywhere."

Decision:
  Approved / Deferred / Declined — plus one sentence why. This mirrors
  PRIORITIZATION_FRAMEWORK.md's "Ignore" category: writing the reason down
  is what stops a declined idea from quietly resurfacing every few weeks
  because nobody remembers it was already considered.

Target Sprint:
  Which sprint this is slated for, if Approved. Leave blank if Deferred or
  Declined — an empty field here is meaningful, not an oversight.
```

## Notes

- **One request per submission.** If a tester lists five things in one message, split them into five entries before triage — otherwise one popular item and one irrelevant one get bundled into the same priority decision.
- **Look for the same "Problem" across multiple testers before building anything.** A single-tester feature request is a data point, not a mandate — see `PRIORITIZATION_FRAMEWORK.md` and `FOUNDER_PLAYBOOK.md`'s note on not overreacting to one person's opinion.
- Requests that are really bugs in disguise ("it should let me search leads by phone number" when search silently only matches names) belong in `BUG_REPORT_TEMPLATE.md` instead — if the current behavior contradicts what the product already claims to do, it's a bug, not a feature request.
