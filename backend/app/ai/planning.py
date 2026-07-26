"""Action Planning (Sprint 58) — readiness checking before tool exposure.

Builds directly on Sprint 57 (app/ai/intent.py): once a message is
classified ACTION and Stage 2 has picked a tool category (Calendar, CRM,
...), this module decides whether the message actually contains enough
information to act, before any tool schema reaches the model. An
incomplete request ("Book a meeting." — no date, no time) never sees a
tool schema at all; the caller instead gets a short, structured hint
describing what's missing, which app/ai/prompts.py folds into the system
prompt so the model can ask a single natural follow-up question in its own
words — this module never writes customer-facing text itself (see
plan_action's docstring).

Like Stage 1/2, this is pure, deterministic text-pattern matching over the
current message only: no LLM call, no network request, no persisted state.
It does not (and, without a schema change to store per-conversation slot
state, cannot) remember a field supplied in an earlier turn — see
PROGRESS.md / this sprint's deliverables for why that's an explicit,
documented scope boundary rather than an oversight.

Extending with a new action's readiness rule means adding one ActionProfile
entry to _ACTION_PROFILES below — no other code changes. This is
deliberately independent of app/ai/intent.py's own Stage 2 category
registry (different axis: intent.py picks *which tool group*, this module
picks *whether that group is withheld pending more detail*) — so adding a
profile here never needs to touch intent.py, and vice versa.

ActionPlan.action (Sprint 59) — the matched profile's name (e.g.
"calendar_booking") — is consumed by app/ai/governance.py to look up an
execution policy once a request is ready, without a third parallel keyword
classifier: governance keys off the same action identity this module
already computes, rather than re-detecting it.

Sprint 75 (DEC-045): plan_action() is unchanged (still the single-domain
path, now implemented via the shared _plan_for_profiles() helper so its
behaviour is provably identical, not just similar). plan_actions() is
additive: one ActionPlan per requested domain, for app/ai/plan.py to turn
into a multi-domain ExecutionPlan. ActionProfile gained a `domain` field
(calendar/crm) so plan_actions() can filter to "just this domain's
profiles" without inferring it from the action name string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_DATE_RE = re.compile(
    r"\b(today|tomorrow|tonight|next\s+\w+|this\s+\w+|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{1,2}/\d{1,2})\b",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"\b\d{1,2}(:\d{2})?\s?(am|pm)\b|\b\d{1,2}:\d{2}\b", re.IGNORECASE)
# A qualifier that disambiguates *which* appointment is meant — a date/time
# reference, or an explicit relative reference like "my next appointment".
_APPOINTMENT_REFERENCE_RE = re.compile(
    r"\b(next|upcoming|today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{1,2}(:\d{2})?\s?(am|pm)|\d{1,2}/\d{1,2})\b",
    re.IGNORECASE,
)
# Presence-only detector: a capitalized token after "for" — a lightweight
# proper-noun heuristic, not real name extraction. See "Tradeoffs" in this
# sprint's deliverables for the known lowercase-name limitation.
_CUSTOMER_NAME_RE = re.compile(r"\bfor\s+([A-Z][a-z]+)\b")
_CONTACT_RE = re.compile(r"\b(\+?\d[\d\-\s]{6,}\d|[\w.+-]+@[\w-]+\.\w{2,})\b")


@dataclass(frozen=True)
class RequiredField:
    name: str
    detector: re.Pattern[str]
    hint: str  # short description folded into the system prompt — never shown to the customer verbatim


@dataclass(frozen=True)
class ActionProfile:
    name: str
    # Sprint 75 (DEC-045): which app/ai/intent.py Stage 2 category this
    # profile belongs to — lets plan_actions() below filter to "just this
    # domain's profiles" without inferring it from the action name string.
    domain: str
    trigger_keywords: tuple[str, ...]
    required: tuple[RequiredField, ...]
    optional_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionPlan:
    ready: bool
    action: str | None = None
    missing_field: str | None = None
    clarification_hint: str | None = None


# Checked in this order: cancel/reschedule before booking, since a message
# like "reschedule my meeting" would otherwise also match booking's
# "schedule" trigger via naive substring matching (word-boundary matching
# below avoids that specific collision, but the more specific profiles are
# still checked first on principle — the narrower rule should win).
#
# Calendar booking — Requires: date, time. Optional: attendee, notes
# (per this sprint's Requirements section; the illustrative dialogue also
# asks about the attendee first for a bare "Book a meeting." — since
# attendee is explicitly Optional in the structured spec, this
# implementation treats date as the first blocking question instead; see
# deliverables for this call-out).
_ACTION_PROFILES: tuple[ActionProfile, ...] = (
    ActionProfile(
        name="calendar_cancel",
        domain="calendar",
        trigger_keywords=("cancel",),
        required=(
            RequiredField(
                "appointment_reference",
                _APPOINTMENT_REFERENCE_RE,
                "ask which appointment they mean (e.g. its date, or that it's their next one)",
            ),
        ),
    ),
    ActionProfile(
        name="calendar_reschedule",
        domain="calendar",
        trigger_keywords=("reschedule",),
        required=(
            RequiredField("date", _DATE_RE, "ask what the new date should be"),
            RequiredField("time", _TIME_RE, "ask what the new time should be"),
        ),
    ),
    ActionProfile(
        name="calendar_booking",
        domain="calendar",
        trigger_keywords=("book", "schedule"),
        required=(
            RequiredField("date", _DATE_RE, "ask what date this should be on"),
            RequiredField("time", _TIME_RE, "ask what time this should be at"),
        ),
        optional_fields=("attendee", "notes"),
    ),
    ActionProfile(
        name="crm_lead",
        domain="crm",
        trigger_keywords=("lead",),
        required=(
            RequiredField("customer_name", _CUSTOMER_NAME_RE, "ask for the customer's name"),
        ),
        optional_fields=("phone", "email", "notes"),
    ),
)


def _plan_for_profiles(text: str, profiles: tuple[ActionProfile, ...]) -> ActionPlan:
    """Checks an Action-classified message against the first matching
    profile's required fields, in the given profiles' order.

    Returns ready=True (no clarification) whenever no profile's trigger
    keywords match — this module only ever *withholds* tools Stage 2
    already selected pending more detail; it never blocks a request Sprint
    57 would otherwise have allowed through and for which no readiness
    rule has been defined yet (a genuinely new/unsupported action degrades
    to Sprint 57's existing behaviour, not a hard stop).
    """
    lower = text.lower()
    for profile in profiles:
        if not any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in profile.trigger_keywords):
            continue
        missing = next((f for f in profile.required if not f.detector.search(text)), None)
        if missing is not None:
            return ActionPlan(
                ready=False,
                action=profile.name,
                missing_field=missing.name,
                clarification_hint=missing.hint,
            )
        return ActionPlan(ready=True, action=profile.name)
    return ActionPlan(ready=True)


def plan_action(text: str) -> ActionPlan:
    """Checks an Action-classified message against every known profile, in
    _ACTION_PROFILES order — the single-domain path every caller before
    Sprint 75 uses. Byte-for-byte the same behaviour as before Sprint 75;
    only its implementation now goes through the shared helper above.
    """
    return _plan_for_profiles(text, _ACTION_PROFILES)


def plan_actions(text: str, domains: list[str]) -> list[ActionPlan]:
    """Sprint 75 (DEC-045): one ActionPlan per requested domain, in the
    given order — app/ai/intent.py::domains_for_action() is what decides
    that order; this module only ever answers "is *this* domain's action
    ready," the same question plan_action() already asked for a single,
    implicit domain. A domain with no matching profile in it behaves
    exactly like plan_action()'s own "no profile matched at all" case
    (ready=True, action=None) — pass-through, not a block.
    """
    return [
        _plan_for_profiles(text, tuple(p for p in _ACTION_PROFILES if p.domain == domain))
        for domain in domains
    ]
