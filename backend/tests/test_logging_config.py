"""Tests for app/main.py's app-logger configuration (Section A5).

Python's root logger defaults to level WARNING with no handler attached, so
every `logging.getLogger(__name__)` call under app.* was silently dropping
INFO records before this fix — only WARNING/ERROR ever surfaced, via
Python's last-resort stderr fallback. `_configure_app_logging()` attaches
one handler directly to the "app" logger (the shared ancestor of every
app.* module logger) and stops propagation there, so it can't interact with
uvicorn's own loggers or create duplicate lines. See app/main.py for the
full design rationale.
"""

import logging

import app.main as app_main


def test_app_logger_is_configured_for_info_with_our_handler():
    # pytest's own logging plugin attaches its LogCaptureHandler directly to
    # any non-propagating logger it finds (see _pytest/logging.py's
    # catching_logs) -- exactly because of loggers like this one -- so
    # app_logger.handlers legitimately holds more than just our own handler
    # by the time an individual test runs. Assert ours is present rather
    # than asserting an exact count.
    app_logger = logging.getLogger("app")

    assert app_logger.level == logging.INFO
    assert app_logger.propagate is False
    assert any(
        type(h) is logging.StreamHandler and h.formatter is not None
        for h in app_logger.handlers
    )


def test_reconfiguring_is_a_no_op_and_never_adds_a_second_handler():
    """Guards against duplicate log lines if _configure_app_logging() ever
    runs again in the same process (e.g. module re-import)."""
    app_logger = logging.getLogger("app")
    before = list(app_logger.handlers)

    app_main._configure_app_logging()
    app_main._configure_app_logging()

    assert app_logger.handlers == before


def test_module_logger_info_is_actually_emitted_not_silently_dropped(caplog):
    """The exact regression this fix addresses: before it, a plain
    `logging.getLogger(__name__).info(...)` anywhere under app.* (e.g.
    app.services.replies, app.ai.processing) was discarded before reaching
    any handler, because its effective level resolved to the root logger's
    default WARNING. A real module logger's INFO call must now be captured."""
    logger = logging.getLogger("app.services.replies")

    with caplog.at_level(logging.INFO, logger="app.services.replies"):
        logger.info("A5 regression marker: info should not be dropped")

    assert any(
        "A5 regression marker" in record.message and record.levelno == logging.INFO
        for record in caplog.records
    )


def test_module_logger_warning_and_exception_still_work(caplog):
    """WARNING/ERROR were already visible before this fix (via Python's
    last-resort handler) — confirms that behavior is preserved, just now
    via this app's own handler instead of the implicit fallback."""
    logger = logging.getLogger("app.services.replies")

    with caplog.at_level(logging.INFO, logger="app.services.replies"):
        logger.warning("A5 regression marker: warning")
        try:
            raise ValueError("a5 regression marker: boom")
        except ValueError:
            logger.exception("A5 regression marker: exception")

    levels = [r.levelno for r in caplog.records if "A5 regression marker" in r.message]
    assert logging.WARNING in levels
    assert logging.ERROR in levels
