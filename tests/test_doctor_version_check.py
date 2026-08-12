"""`mi-mcp doctor` release check.

Why this exists: on 2026-08-04 a user was running 0.2.5 while 0.2.7 was current,
and reported "the workspace tools don't exist". They weren't missing — the version
was. Nothing in the tool ever said so: doctor reported binary, PATH, wrapper, key,
allowlist, vault and wiring, and not one word about the version it was running.

Pinned here:
  1. behind → a visible ✗ with the upgrade command for THIS install method;
  2. unreachable PyPI → "unknown", never silently "up to date";
  3. opt-out makes NO network call at all;
  4. the version source is the SIMPLE INDEX, not /pypi/<p>/json (which served a
     stale cache minutes after 0.2.7 published — the exact failure mode this check
     is supposed to catch);
  5. ordering is numeric, so 0.2.10 > 0.2.9.

Network-free: the PyPI lookup is monkeypatched everywhere.
"""

from __future__ import annotations

import pytest

from mi_mcp import cli


@pytest.fixture(autouse=True)
def _mirror_channel_silent(monkeypatch):
    """This file pins the **PyPI** channel. Doctor consults a second one since
    #1347 (the public GitHub mirror), which has its own file —
    `test_doctor_mirror_channel.py`. Stub it to "unknown" here so each test below
    still exercises exactly the PyPI behaviour it was written for, and so no test
    in this file reaches the network to find out.
    """
    monkeypatch.setattr(cli, "_latest_mirror_version", lambda *a, **k: None)


# --- 5. version ordering -----------------------------------------------------

@pytest.mark.parametrize("lo,hi", [
    ("0.2.5", "0.2.7"),
    ("0.2.9", "0.2.10"),   # the classic string-compare bug: "0.2.9" > "0.2.10"
    ("0.9.0", "1.0.0"),
    ("1.0.0", "1.0.1"),
])
def test_version_ordering_is_numeric(lo, hi):
    assert cli._version_tuple(lo) < cli._version_tuple(hi)


def test_equal_versions_are_not_behind():
    assert not (cli._version_tuple("0.2.7") > cli._version_tuple("0.2.7"))


def test_garbage_version_does_not_raise():
    assert cli._version_tuple("") == (-1,)
    assert cli._version_tuple("not.a.version") == (-1, -1, -1)


# --- 4. the source must be the simple index ----------------------------------

def test_lookup_uses_the_simple_index_not_the_aggregate_json(monkeypatch):
    """The aggregate /pypi/<project>/json endpoint is CDN-cached and was observed
    serving a stale version minutes after a publish. Reading it would make doctor
    confidently report 'latest' to someone who is behind."""
    seen: dict = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"versions": ["0.2.5", "0.2.7"]}'

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["accept"] = req.headers.get("Accept")
        return _Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert cli._latest_pypi_version() == "0.2.7"
    assert seen["url"] == "https://pypi.org/simple/memoryintelligence-mcp/"
    assert "/pypi/" not in seen["url"] or "/simple/" in seen["url"]
    assert "simple" in (seen["accept"] or "")


def test_lookup_picks_the_max_not_the_last(monkeypatch):
    """The index order is not guaranteed to be sorted."""
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"versions": ["0.2.10", "0.2.7", "0.2.9"]}'

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert cli._latest_pypi_version() == "0.2.10"


# --- 2. failures are "unknown", never "fine" ---------------------------------

@pytest.mark.parametrize("boom", [
    OSError("offline"), TimeoutError("slow"), ValueError("bad json"),
])
def test_unreachable_pypi_returns_none_and_never_raises(monkeypatch, boom):
    import urllib.request

    def fake_urlopen(*a, **k):
        raise boom

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert cli._latest_pypi_version() is None


def test_doctor_reports_unknown_rather_than_up_to_date(monkeypatch, capsys, tmp_path):
    """An offline machine must not be told it is current — that is the same class
    of lie as reading the stale endpoint."""
    monkeypatch.setattr(cli, "_latest_pypi_version", lambda *a, **k: None)
    monkeypatch.delenv(cli.NO_VERSION_CHECK_ENV, raising=False)
    cli.cmd_doctor(["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert "latest unknown" in out
    assert "(latest)" not in out


# --- 1. behind → visible, with the right command -----------------------------

def test_doctor_flags_a_behind_version_with_an_upgrade_command(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "_latest_pypi_version", lambda *a, **k: "9.9.9")
    monkeypatch.setattr(cli, "_upgrade_command", lambda: "uv tool upgrade memoryintelligence-mcp")
    monkeypatch.delenv(cli.NO_VERSION_CHECK_ENV, raising=False)
    cli.cmd_doctor(["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert "9.9.9 available" in out
    assert "[✗] version" in out
    assert "uv tool upgrade memoryintelligence-mcp" in out
    # wire is mandatory across the 0.2.6 rename — the upgrade alone leaves a
    # config pointing at a server id that no longer announces itself.
    assert "mi-mcp wire" in out


def test_being_behind_does_not_fail_doctor(monkeypatch, tmp_path):
    """Out of date is not broken. It must not flip the exit code, or CI/scripts
    that gate on `mi-mcp doctor` start failing the day a release lands."""
    monkeypatch.setattr(cli, "_latest_pypi_version", lambda *a, **k: "9.9.9")
    monkeypatch.delenv(cli.NO_VERSION_CHECK_ENV, raising=False)
    rc_behind = cli.cmd_doctor(["--home", str(tmp_path)])
    monkeypatch.setattr(cli, "_latest_pypi_version", lambda *a, **k: "0.0.1")
    rc_current = cli.cmd_doctor(["--home", str(tmp_path)])
    assert rc_behind == rc_current


# --- 3. opt-out makes no call ------------------------------------------------

@pytest.mark.parametrize("how", ["flag", "env"])
def test_opt_out_makes_no_network_call(monkeypatch, capsys, tmp_path, how):
    """This is a privacy-forward product; 'skip the check' has to mean no request
    was made, not a request whose result was ignored."""
    called: list = []
    monkeypatch.setattr(cli, "_latest_pypi_version",
                        lambda *a, **k: called.append(1) or "9.9.9")
    argv = ["--home", str(tmp_path)]
    if how == "flag":
        monkeypatch.delenv(cli.NO_VERSION_CHECK_ENV, raising=False)
        argv.append("--no-version-check")
    else:
        monkeypatch.setenv(cli.NO_VERSION_CHECK_ENV, "1")
    cli.cmd_doctor(argv)
    assert called == [], "opt-out still hit the network"
    assert "release check skipped" in capsys.readouterr().out


# --- the upgrade command matches the install method --------------------------

@pytest.mark.parametrize("prefix,expected", [
    ("/Users/x/.local/share/uv/tools/memoryintelligence-mcp", "uv tool upgrade"),
    ("/Users/x/.local/pipx/venvs/memoryintelligence-mcp", "pipx upgrade"),
])
def test_upgrade_command_matches_the_install_method(monkeypatch, prefix, expected):
    """Telling a uv-tool user to run pip is a dead end — `pip` may not even exist
    (Homebrew python is PEP-668 externally managed). That happened on 2026-08-04."""
    monkeypatch.setattr(cli.sys, "prefix", prefix)
    monkeypatch.delenv("PIPX_HOME", raising=False)
    assert cli._upgrade_command().startswith(expected)


def test_upgrade_command_falls_back_to_pip_for_a_plain_venv(monkeypatch):
    monkeypatch.setattr(cli.sys, "prefix", "/Users/x/proj/.venv")
    monkeypatch.delenv("PIPX_HOME", raising=False)
    cmd = cli._upgrade_command()
    assert "-m pip install --upgrade memoryintelligence-mcp" in cmd
