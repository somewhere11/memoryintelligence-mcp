"""`mi-mcp doctor` must check BOTH release channels, not just PyPI (#1347).

This package ships on two channels — PyPI and the public GitHub mirror
`somewhere11/memoryintelligence-mcp` — and they have already diverged in production.
0.2.6 was published, tagged and installable from the mirror while PyPI went straight
0.2.5 → 0.2.7. For ~20 hours a mirror-installed user on 0.2.6 could run `mi-mcp
doctor` and, because the check read PyPI alone, be told **"0.2.6 (latest)"** — a green
tick — while `main` was already moving to 0.2.7.

That is the same false-reassurance class the unreachable-PyPI branch was deliberately
written to avoid ("latest unknown", never "up to date"). The divergence branch simply
never got the same treatment.

Pinned here:
  1. the mirror version is read from the mirror's own ``pyproject.toml``;
  2. "latest" is the max ACROSS channels, so being ahead of PyPI is not "latest";
  3. when the channels DISAGREE doctor says so explicitly — even when the user is on
     the newest of the two, because a silent divergence is the bug;
  4. either channel unreachable degrades to "unknown", never to green;
  5. an opt-out still makes NO network call, to either channel;
  6. the mirror lookup never raises, whatever the network does.

Network-free: every lookup is monkeypatched.
"""

from __future__ import annotations

import pytest

from mi_mcp import cli


class _Resp:
    def __init__(self, body: bytes):
        self._b = body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


MIRROR_PYPROJECT = (
    b"[project]\n"
    b'name = "memoryintelligence-mcp"\n'
    b'version = "0.2.6"\n'
    b'requires-python = ">=3.10"\n'
)


# --- 1 / 6. the mirror lookup ------------------------------------------------

def test_mirror_version_is_read_from_mirror_pyproject(monkeypatch):
    seen = {}
    import urllib.request

    def fake_urlopen(req, *a, **k):
        seen["url"] = getattr(req, "full_url", str(req))
        return _Resp(MIRROR_PYPROJECT)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert cli._latest_mirror_version() == "0.2.6"
    assert "memoryintelligence-mcp" in seen["url"]


@pytest.mark.parametrize("boom", [OSError("dns"), ValueError("garbage"), TimeoutError()])
def test_unreachable_mirror_returns_none_and_never_raises(monkeypatch, boom):
    import urllib.request

    def fake_urlopen(*a, **k):
        raise boom

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert cli._latest_mirror_version() is None


def test_mirror_pyproject_without_a_version_is_none(monkeypatch):
    import urllib.request

    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *a, **k: _Resp(b"[project]\nname = 'x'\n"),
    )
    assert cli._latest_mirror_version() is None


def test_mirror_reads_the_project_version_not_requires_python(monkeypatch):
    """`requires-python = ">=3.10"` also contains a dotted number. A sloppy regex
    picks it up and reports the Python floor as the package version."""
    import urllib.request

    body = (
        b"[project]\n"
        b'requires-python = ">=3.10"\n'
        b'version = "0.2.11"\n'
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    assert cli._latest_mirror_version() == "0.2.11"


# --- 2 / 3 / 4. the combined reading -----------------------------------------

def _combined(monkeypatch, pypi, mirror):
    monkeypatch.setattr(cli, "_latest_pypi_version", lambda *a, **k: pypi)
    monkeypatch.setattr(cli, "_latest_mirror_version", lambda *a, **k: mirror)
    return cli._latest_release()


def test_latest_is_the_max_across_channels(monkeypatch):
    """THE #1347 BUG. Mirror ahead of PyPI must not read as 'latest'."""
    latest, channels = _combined(monkeypatch, pypi="0.2.5", mirror="0.2.6")
    assert latest == "0.2.6"
    assert channels == {"PyPI": "0.2.5", "mirror": "0.2.6"}


def test_latest_ordering_is_numeric_across_channels(monkeypatch):
    latest, _ = _combined(monkeypatch, pypi="0.2.9", mirror="0.2.10")
    assert latest == "0.2.10"


def test_channels_agreeing_reports_no_divergence(monkeypatch):
    latest, channels = _combined(monkeypatch, pypi="0.2.10", mirror="0.2.10")
    assert latest == "0.2.10"
    assert not cli._channels_diverge(channels)


def test_channels_disagreeing_is_detected(monkeypatch):
    _, channels = _combined(monkeypatch, pypi="0.2.5", mirror="0.2.6")
    assert cli._channels_diverge(channels)


def test_one_channel_unknown_is_not_divergence(monkeypatch):
    """Unknown is not disagreement. Do not cry wolf when simply offline."""
    _, channels = _combined(monkeypatch, pypi="0.2.10", mirror=None)
    assert not cli._channels_diverge(channels)


def test_both_unreachable_is_unknown(monkeypatch):
    latest, channels = _combined(monkeypatch, pypi=None, mirror=None)
    assert latest is None
    assert channels == {"PyPI": None, "mirror": None}


def test_single_reachable_channel_still_yields_a_latest(monkeypatch):
    latest, _ = _combined(monkeypatch, pypi=None, mirror="0.2.9")
    assert latest == "0.2.9"


# --- 5. opt-out makes no network call, to EITHER channel ---------------------

def test_opt_out_makes_no_network_call_to_either_channel(monkeypatch, capsys, tmp_path):
    import urllib.request

    def explode(*a, **k):
        raise AssertionError("doctor made a network call despite the opt-out")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    monkeypatch.setenv(cli.NO_VERSION_CHECK_ENV, "1")
    monkeypatch.setattr(cli.paths, "mcp_config_dir", lambda **k: tmp_path)
    cli.cmd_doctor([])
    assert "release check skipped" in capsys.readouterr().out
