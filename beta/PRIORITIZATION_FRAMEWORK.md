# Prioritization Framework

Every bug report and feature request gets exactly one of these five labels. The point of having five (not just "important / not important") is that bugs and feature requests need *different* urgency logic, and a two-bucket system collapses that distinction — "critical bug" and "nice to have" don't sit on the same axis as "would be cool someday."

## Critical Bug — fix immediately, same day

**Definition**: Blocks a user from completing a core workflow, with no workaround. Data loss, security exposure, or a crash in the primary path (sign up → onboard → Demo Chat → CRM) all qualify automatically regardless of how many people hit it.

**Why this category exists**: A single critical bug in a 5–10 person beta can silently end someone's participation — they hit it once, conclude the product doesn't work, and quietly stop coming back without ever filing anything. You often won't get a report; you'll get silence on the tracking board. Treat "went quiet right after a session" as a critical-bug signal worth investigating even without an explicit report.

## High Priority — fix this week

**Definition**: Significantly hurts usability but has a workaround, or breaks a secondary (not primary) workflow. Confusing enough that multiple testers hit the same wall, or one tester hit it and it clearly cost them real time/trust.

**Why this category exists**: Not urgent enough to drop everything, but urgent enough that letting it sit for the full beta duration means every subsequent tester hits the same friction. The cost compounds with each new user, unlike a critical bug which is usually caught (and fixed) on day one.

## Medium Priority — queue for after the beta, or a slow week during it

**Definition**: A real improvement to the experience, but the current behavior isn't broken or blocking — just not as good as it could be.

**Why this category exists**: This is where most feedback actually lands, and where the temptation to build immediately is strongest because the ideas are good. Building medium-priority items mid-beta risks introducing new bugs into a codebase you're actively trying to observe under real usage — resist unless it's genuinely cheap and safe.

## Nice to Have — backlog, revisit later with more evidence

**Definition**: Would be a genuine improvement, but low urgency and no clear cost to waiting. Often surfaces as "it would be cool if..." rather than "I needed to..."

**Why this category exists**: Distinguishes "this would help" from "this would help *right now*, *this specific person*." A backlog of nice-to-haves is healthy — it means people are engaged enough to imagine more uses for the product. Don't let a growing backlog create pressure to build during the beta itself; that's what Part 8 (the founder playbook) is for.

## Ignore — explicitly decided not to act on, and say why

**Definition**: A single tester's personal preference that contradicts the product's actual positioning or target user, a one-off outlier that doesn't recur, or feedback based on a misunderstanding that's better solved with a one-line explanation than a feature.

**Why this category exists**: "Ignore" is a real, named category — not a silent drop — specifically so you have a record of *why* something wasn't actioned. Without it, the same rejected idea tends to resurface every few weeks because nobody remembers it was already considered and consciously declined. Write one sentence for why it's here; that sentence is what saves you from re-litigating it later.

## The actual triage question

For every new item, ask in this order:
1. Does it block a core workflow with no workaround? → **Critical Bug.**
2. Is it a bug (not a request) that meaningfully hurts usability? → **High Priority.**
3. Is it a feature request more than one tester has independently raised? → at least **Medium**, lean **High** if it's blocking real usage for those testers.
4. Is it a single tester's idea, with real business impact behind it? → **Medium** or **Nice to Have**, based on frequency/impact from `FEATURE_REQUEST_TEMPLATE.md`.
5. Is it a preference that conflicts with the product's actual direction, or a one-off you can't reproduce? → **Ignore**, with the reason written down.
