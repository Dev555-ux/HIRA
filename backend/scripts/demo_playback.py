"""Playback engine for "THE ORCHESTRATION" (HIRA Studio launch film).

Reproduces the approved Beat Board against the Alder Street Dental demo
business (see scripts/seed_demo_alder_street.py, which must be run first).

For each beat, this script only ever does the customer's half of the
exchange — it injects a real inbound WhatsApp-shaped message through the
same code path app/webhooks/whatsapp.py uses (MessagingService.record_inbound
+ app.ai.processing.generate_reply_into_session), then pauses. It never
simulates a human clicking Approve/Escalate/Publish — the operator performs
that real action in the real app during the pause. That split is what makes
the resulting recordings real screen captures instead of fabricated ones.

Usage (run from the backend/ directory):

    .venv/bin/python scripts/demo_playback.py --scene beat01
    .venv/bin/python scripts/demo_playback.py --scene beat07
    .venv/bin/python scripts/demo_playback.py --scene full

Some beats require a specific Business.mode (Assisted or Autonomous) — see
the Production Package's Phase A/B/C schedule. Running a beat against the
wrong mode raises immediately with the exact seeder command to fix it,
rather than silently flipping the flag out from under a take in progress.
"""

from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.ai.processing import generate_reply_into_session
from app.channels.base.message import NormalizedMessage
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Business
from app.services.messaging_service import MessagingService

BUSINESS_NAME = "Alder Street Dental"


@dataclass(frozen=True)
class MessageTrigger:
    persona: str
    phone: str
    text: str


@dataclass(frozen=True)
class Scene:
    id: str
    label: str
    required_mode: str | None  # "assisted" | "autonomous" | None (not applicable)
    triggers: tuple[MessageTrigger, ...] = ()
    instruction: str = ""


SCENES: list[Scene] = [
    Scene(
        "beat01",
        "First message — Priya Shah",
        "assisted",
        (MessageTrigger("Priya Shah", "+15550002001", "Hi, can I book a cleaning this week?"),),
        "Record SR_001 (Inbox: message arrives, draft comes to rest).",
    ),
    Scene(
        "beat02",
        "Approval — Priya's draft",
        "assisted",
        (),
        "In the app, approve Priya's draft. Record SR_002.",
    ),
    Scene(
        "beat03",
        "Booking outcome — Priya's slot fills",
        "assisted",
        (),
        "Record SR_003 once Priya's appointment appears on the calendar.",
    ),
    Scene(
        "beat04",
        "Second customer, parallel — Marcus Webb",
        "assisted",
        (MessageTrigger("Marcus Webb", "+15550002002", "Are you open Saturdays?"),),
        "Record SR_004.",
    ),
    Scene(
        "beat05",
        "Approval — Marcus's draft",
        "assisted",
        (),
        "Approve Marcus's draft. Record SR_005.",
    ),
    Scene(
        "beat06",
        "Reschedule — Dana Ostrowski",
        "assisted",
        (
            MessageTrigger(
                "Dana Ostrowski", "+15550002003", "Can we move my cleaning to Friday instead?"
            ),
        ),
        "Record SR_006. (Also record SR_019, Dana's cancellation — batched here per the Recording Schedule "
        "even though it appears later in the finished film; see Beat 16.)",
    ),
    Scene(
        "beat07",
        "Escalation trigger — Tom Reyes",
        "assisted",
        (
            MessageTrigger(
                "Tom Reyes", "+15550002004", "Can you see my 2-year-old for a first visit?"
            ),
        ),
        'HIRA will draft an honest "not sure" reply (no matching KB fact — this is expected, not a bug). '
        "Record SR_007 with the draft visible.",
    ),
    Scene(
        "beat08",
        "Escalation resolution — Tom Reyes",
        "assisted",
        (),
        "In the app, click Escalate on Tom's draft (not Approve). Record SR_008. Then resolve it as the "
        "owner. Record SR_009.",
    ),
    Scene(
        "beat09",
        "Knowledge import",
        None,
        (),
        "No backend trigger for this beat. In the real app: paste the live new-patient-paperwork URL "
        "into Knowledge, run the import, review, and publish. Record SR_010, then SR_011.",
    ),
    Scene(
        "beat10",
        "Grounded answer — Elena Cho",
        "assisted",
        (
            MessageTrigger(
                "Elena Cho", "+15550002005", "What paperwork do I need to bring as a new patient?"
            ),
        ),
        "Run this only after Beat 09's import is published. Record SR_012.",
    ),
    Scene(
        "beat11",
        "Cluster — Sam Ortiz + Nora Fielding",
        "assisted",
        (
            MessageTrigger(
                "Sam Ortiz", "+15550002006", "Do you have anything open next Tuesday morning?"
            ),
            MessageTrigger(
                "Nora Fielding", "+15550002007", "Need to push my appointment back an hour"
            ),
        ),
        "Record SR_013 (both unread together). Approve Sam's draft — record SR_014. Confirm Nora's "
        "reschedule — record SR_028.",
    ),
    Scene(
        "beat12",
        "First autonomous exchange — Alicia Brandt",
        "autonomous",
        (
            MessageTrigger(
                "Alicia Brandt", "+15550002008", "Do you have any filling appointments this week?"
            ),
        ),
        "Record SR_015 (reply already sent, nothing in the queue).",
    ),
    Scene(
        "beat13",
        "Autonomous booking — Alicia Brandt",
        "autonomous",
        (),
        "Likely resolved in the same turn as Beat 12 (a single execution plan can include the booking "
        "tool call). Record SR_016 once the calendar updates; no new trigger needed.",
    ),
    Scene(
        "beat14",
        "Returning lead — Renee Castillo",
        "autonomous",
        (
            MessageTrigger(
                "Renee Castillo",
                "+15550002009",
                "Hi! Is the whitening thing you mentioned still available?",
            ),
        ),
        "Record SR_017. HIRA's reply should reflect her existing Lead notes without asking her to repeat them.",
    ),
    Scene(
        "beat15",
        "Second autonomous wave — Devon, Ibrahim, Layla",
        "autonomous",
        (
            MessageTrigger("Devon Park", "+15550002010", "Do you take Delta Dental?"),
            MessageTrigger("Ibrahim Farooq", "+15550002011", "What are your hours on Saturday?"),
            MessageTrigger("Layla Ahmed", "+15550002012", "Can I book a filling for tomorrow?"),
        ),
        "Record SR_018 (Devon). Record SR_021 (Ibrahim). Record SR_022 once Layla's booking fills the "
        "calendar. These three also supply the footage used in Beat 17's composite.",
    ),
    Scene(
        "beat16",
        "Cancellation — Dana Ostrowski",
        "assisted",
        (MessageTrigger("Dana Ostrowski", "+15550002003", "Actually I need to cancel Friday"),),
        "Per the Recording Schedule this is batched with Beat 06 (SR_019), not filmed here — this scene "
        "exists so --scene beat16 is independently runnable if needed.",
    ),
    Scene(
        "beat17",
        "Peak — convergence",
        None,
        (),
        "Composite beat, no new recording. Assembled in editing from footage already captured in "
        "Beat 12/13 (Alicia), Beat 15 (Ibrahim, Layla), and Beat 18 (Grace). See Production Notes Correction 2.",
    ),
    Scene(
        "beat18",
        "Last held item — Grace Liu",
        "assisted",
        (MessageTrigger("Grace Liu", "+15550002013", "Can I get a cleaning next month sometime?"),),
        "Requires Business.mode switched back to assisted first. Record SR_020 (held). Then approve it in "
        "the app — record SR_023. This same thread is reused for Beat 17's Shot 38.",
    ),
    Scene(
        "beat19",
        "Thinning out",
        None,
        (),
        "No trigger. Pure pacing/transition beat — nothing to record from the product.",
    ),
    Scene(
        "beat20",
        "Last message of the day — Owen Marsh",
        "assisted",
        (
            MessageTrigger(
                "Owen Marsh", "+15550002014", "One more thing — do you validate parking?"
            ),
        ),
        "Record SR_025. Approve it — record SR_026, then record SR_024 (empty inbox) once nothing remains.",
    ),
    Scene(
        "beat21",
        "The full day",
        None,
        (),
        "No trigger. Record SR_027 (calendar pulled back) once every appointment in the film exists.",
    ),
    Scene(
        "beat22",
        "Silence / end card",
        None,
        (),
        "No product recording. Motion Graphics/Typography only (Storyboard Shots 51-53).",
    ),
]

_SCENES_BY_ID = {scene.id: scene for scene in SCENES}


def _assert_ready_for_recording() -> None:
    if settings.llm_provider == "mock":
        raise SystemExit(
            "LLM_PROVIDER is 'mock'. Recording against the mock echo would produce fabricated "
            "drafts, not real ones. Set LLM_PROVIDER to a real provider before running playback."
        )


def _get_business(db) -> Business:
    business = db.scalars(select(Business).where(Business.name == BUSINESS_NAME)).first()
    if business is None:
        raise SystemExit(
            f"No business named {BUSINESS_NAME!r}. Run scripts/seed_demo_alder_street.py first."
        )
    return business


def _run_trigger(db, business: Business, trigger: MessageTrigger) -> None:
    normalized = NormalizedMessage(
        channel="whatsapp",
        external_conversation_id=trigger.phone,
        external_message_id=str(uuid.uuid4()),
        external_sender_id=trigger.phone,
        text=trigger.text,
        sender_display_name=trigger.persona,
        raw={"type": "text"},
    )
    new_inbound = MessagingService(db).record_inbound(business.id, [normalized])
    db.commit()
    if not new_inbound:
        print(f"    (no new message persisted for {trigger.persona} — unexpected duplicate id)")
        return

    conversation_id, message_id, _wa_message_id, text = new_inbound[0]
    print(f"    {trigger.persona} -> {text!r}")

    on_commit_failures = generate_reply_into_session(db, conversation_id, message_id, text)
    try:
        db.commit()
    except Exception:
        for compensate in on_commit_failures:
            compensate()
        db.rollback()
        raise
    print(f"    HIRA responded. (business.mode={business.mode!r})")


def run_scene(db, business: Business, scene: Scene) -> None:
    print(f"\n=== {scene.id.upper()}: {scene.label} ===")

    if scene.required_mode is not None and business.mode != scene.required_mode:
        raise SystemExit(
            f"{scene.id} expects Business.mode={scene.required_mode!r}, but it is currently "
            f"{business.mode!r}.\nFix with: "
            f".venv/bin/python scripts/seed_demo_alder_street.py --mode {scene.required_mode}"
        )

    for trigger in scene.triggers:
        _run_trigger(db, business, trigger)

    if scene.instruction:
        print(f"    >>> {scene.instruction}")
    input("    Press Enter once recorded to continue... ")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--scene", required=True, help="One of: " + ", ".join(_SCENES_BY_ID) + ", or 'full'"
    )
    args = parser.parse_args()

    _assert_ready_for_recording()

    if args.scene == "full":
        selected = SCENES
    elif args.scene in _SCENES_BY_ID:
        selected = [_SCENES_BY_ID[args.scene]]
    else:
        valid = ", ".join(_SCENES_BY_ID)
        raise SystemExit(f"Unknown scene {args.scene!r}. Valid: {valid}, full")

    db = SessionLocal()
    try:
        business = _get_business(db)
        print(f"Playing back against {business.name!r} (mode={business.mode!r})")
        for scene in selected:
            run_scene(db, business, scene)
        print("\nPlayback complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
