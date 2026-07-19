# Founder Playbook — Running the Beta

Practical operating rhythm for the 2–3 weeks a 5–10 person beta typically runs. The theme underneath all of this: **move fast on evidence, slow down on opinion.**

## How often to check logs

- **Daily, briefly** — a few minutes scanning for errors (`request_id`/`status`/`duration_ms` lines from the production hardening work), not a deep audit each time.
- **Immediately after telling someone to try something new** — if you point a tester at a feature, watch the logs while they're using it. You'll see a crash before they finish typing the bug report.
- **Don't build a habit of staring at logs waiting for something to go wrong.** Sentry (once `SENTRY_DSN` is set — see the Sprint 53 certification report) exists specifically so you don't have to be the polling mechanism. Check logs on a schedule, not out of anxiety.

## How often to contact users

- **Day 1**: send the checklist + a specific ask ("try this in the next 2 days, then fill out the form"). Vague asks ("let me know what you think whenever") produce silence.
- **Every 3–4 days**: a short personal check-in to anyone whose "Last active" on the tracking board has gone stale. Not a mass email — a direct message referencing something specific to them ("did you get a chance to try uploading your menu/price list?").
- **Immediately** after fixing a bug they reported. This single habit does more for retention in a beta than almost anything else — it tells them their report mattered and turns a frustrated tester back into an engaged one.
- **Don't** message the whole cohort every time you ship a fix. Most won't have hit that specific bug; a targeted message to the person who reported it lands better than a broadcast.

## When to fix bugs immediately

- Anything labeled **Critical Bug** in the prioritization framework — same day, before doing anything else planned for that day.
- Anything causing a tester to go silent right after hitting it (see `TRACKING_BOARD.md` — treat unexplained inactivity as a possible critical-bug signal, not just as disengagement).
- A security or data-integrity issue, regardless of how many people it's affected so far — the count of people affected isn't the relevant variable for this category.

## When to wait for more evidence

- Anything below Critical/High in the prioritization framework, *especially* feature requests. One tester asking for something is a data point; three independently asking for the same thing is a pattern worth acting on before the beta even ends.
- Anything that would require a real code change mid-beta to a part of the system you're actively trying to observe under real usage. Shipping a fix is sometimes right (see above); shipping a redesign mid-beta muddies whether subsequent feedback is about the original experience or the new one.
- Any temptation to build a Nice-to-Have because it's a fun idea. Beta time is for observing, not building — that's explicitly the frame this sprint was given, and it holds for you as founder too, not just for the AI assistant helping you run it.

## How to avoid overreacting to one person's opinion

- **Separate "this is broken" from "this isn't how I'd do it."** The first is evidence; the second is one person's mental model, which is useful data but not a mandate. `PRIORITIZATION_FRAMEWORK.md`'s "Ignore" category exists precisely so single-opinion feedback gets a conscious, written decision instead of either reflexive action or reflexive dismissal.
- **Weight feedback by how it was given, not just what it says.** A specific, reproducible complaint from someone who used the product for 20 minutes carries more evidentiary weight than a strong opinion from someone who logged in once for two minutes. Both are worth recording; they're not worth the same amount of action.
- **Look for the same problem stated differently by different people before treating it as a pattern.** Two testers separately saying "I couldn't tell if my document actually got used" is a real signal even if neither phrased it the same way. Read across the tracking board and feedback forms periodically specifically looking for this kind of convergence, not just re-reading the loudest single response.
- **Remember the sample size.** With 5–10 users, one strongly negative response is meaningful but is not "20% of my users hate this" in any statistically real sense — it's one person. Treat it as worth investigating, not worth panicking over or reversing a product decision on its own.
- **When in doubt, ask a clarifying question before acting.** "What would have made that clearer?" gets you actionable detail; guessing at what they meant and building a fix for your guess is how you end up solving the wrong problem confidently.
