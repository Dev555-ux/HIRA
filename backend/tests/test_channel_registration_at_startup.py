"""Regression test for a real production bug found while building Sprint 65
PR 1: `app.main` used to import cleanly with the default channel registry
completely empty, because nothing in its import graph imported
`app.channels.whatsapp` (the package whose own `__init__.py` registers
`WhatsAppProvider`) — see `app/channels/__init__.py::register_all()`'s
docstring for the full story.

Deliberately runs in a **subprocess**, not in-process. An in-process test
(`import app.main` inside this same pytest run) would not reliably catch a
regression: pytest collects every test module before running any of them,
and some other test file always imports `app.channels.whatsapp` directly
during collection — which is exactly the mechanism that silently masked
the original bug from the entire 1196-test suite. Only a genuinely fresh
process (matching how `uvicorn app.main:app` actually starts in
production) proves the registration happens without help from test-import
order.
"""

import subprocess
import sys


def test_importing_app_main_registers_whatsapp_in_a_fresh_process():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.main\n"
            "from app.channels.registry import get_default_registry\n"
            "print(get_default_registry().available())",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "whatsapp" in result.stdout, (
        f"Default registry did not contain 'whatsapp' after importing app.main "
        f"in a fresh process. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
