"""Suite-wide guards.

**No test in this package may make a real network call.** Several test files declare
themselves "network-free" in their docstrings, but nothing enforced it, so the
property held only as long as every author remembered. It stopped holding the moment
`mi-mcp doctor` grew a second release-channel lookup (#1347): the existing tests
patched `_latest_pypi_version` and knew nothing about `_latest_mirror_version`, so
five of them silently began fetching `raw.githubusercontent.com` on every run.

Nothing failed loudly. The tests passed — against live data — and would have started
failing only on an offline machine, in a sandboxed CI runner, or on the day the
mirror moved. That is the same shape as the bug #1347 is about: a check that looks
green because it quietly asked the network instead of the thing it claimed to test.

So the guard is autouse and blocks by default. A test that genuinely wants to
exercise transport monkeypatches `urlopen` itself, which takes precedence over this
fixture and is self-documenting at the call site.
"""

from __future__ import annotations

import urllib.request

import pytest


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    def _blocked(req, *a, **k):
        url = getattr(req, "full_url", str(req))
        raise AssertionError(
            f"test made a REAL network call to {url}.\n"
            "The suite is network-free by contract. Monkeypatch the lookup "
            "(e.g. cli._latest_pypi_version / cli._latest_mirror_version) or "
            "urllib.request.urlopen in the test itself."
        )

    monkeypatch.setattr(urllib.request, "urlopen", _blocked)
