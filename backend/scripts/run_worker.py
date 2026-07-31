"""CLI entry point for the outbox worker daemon (Sprint 64 — IMP-001, PR 3).

Runs one worker process that drains `job_outbox` until it receives SIGTERM /
SIGINT (Ctrl-C), then finishes its in-flight job and exits cleanly. Scale
horizontally by running more copies — ``FOR UPDATE SKIP LOCKED`` lets them share
the queue without contention.

Run from the backend/ directory:

    .venv/bin/python scripts/run_worker.py

All tuning (batch size, poll interval, zombie timeout, backoff) comes from the
`outbox_*` settings in app/core/config.py / the environment. Handlers must be
imported before the loop starts so they register themselves; import them here as
they land in later PRs.
"""

from __future__ import annotations

import logging

from app.jobs.worker import OutboxWorker

# Importing this module registers the AI-reply handler (PR 4) so the worker can
# discover it. Every production task handler must be imported here before the
# loop starts polling; add later workflows' modules alongside it as they land.
import app.ai.tasks  # noqa: F401 — imported for its handler-registration side effect


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    OutboxWorker().run()


if __name__ == "__main__":
    main()
