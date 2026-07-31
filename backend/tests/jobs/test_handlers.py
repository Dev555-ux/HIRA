"""PR 3 (ADR-001 / IMP-001) — tests for the task handler registry.

The registry is a module-level singleton, so every test cleans it via the
autouse fixture to stay isolated. Worker dispatch behaviour is tested in
test_worker.py; this file covers only registration mechanics.
"""

import pytest

from app.jobs import handlers


@pytest.fixture(autouse=True)
def _clean_registry():
    handlers.clear_registry()
    yield
    handlers.clear_registry()


def _noop(db, job):
    return None


class TestRegistration:
    def test_register_decorator_registers_and_returns_the_function(self):
        @handlers.register("send_email")
        def handler(db, job):
            return None

        assert handlers.is_registered("send_email")
        assert handlers.get_handler("send_email") is handler

    def test_register_handler_imperative_form(self):
        handlers.register_handler("send_sms", _noop)
        assert handlers.get_handler("send_sms") is _noop

    def test_duplicate_registration_is_rejected(self):
        handlers.register_handler("dup", _noop)
        with pytest.raises(ValueError, match="already registered"):
            handlers.register_handler("dup", _noop)

    def test_blank_task_name_is_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            handlers.register_handler("   ", _noop)

    def test_task_name_is_stripped(self):
        handlers.register_handler("  padded  ", _noop)
        assert handlers.is_registered("padded")


class TestLookup:
    def test_unknown_task_returns_none_rather_than_raising(self):
        # The worker relies on this: an unknown task must not raise here.
        assert handlers.get_handler("nope") is None

    def test_registered_tasks_is_sorted_snapshot(self):
        handlers.register_handler("b", _noop)
        handlers.register_handler("a", _noop)
        assert handlers.registered_tasks() == ("a", "b")

    def test_unregister_removes_a_handler(self):
        handlers.register_handler("temp", _noop)
        handlers.unregister("temp")
        assert not handlers.is_registered("temp")
        # Unregistering something absent is a no-op, not an error.
        handlers.unregister("temp")


class TestErrorTypes:
    def test_transient_and_permanent_are_job_errors(self):
        assert issubclass(handlers.TransientJobError, handlers.JobError)
        assert issubclass(handlers.PermanentJobError, handlers.JobError)
