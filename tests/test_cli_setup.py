"""Tests for `mi-mcp setup` (alias `init`) — the one-command onboarding flow.

All run against a temp HOME. The load-bearing security assertion is unchanged
from `wire`: the API key is stored OUTSIDE every MCP config (in a chmod-600
keyfile here, or the macOS Keychain on a real Mac) and is NEVER written into a
config file. Setup collapses store-key → wire → opt-in → verify into one call.
"""

import json
import os
import stat
import sys

import pytest

import mi_mcp.cli as cli

SERVER_KEY, run_admin = cli.SERVER_KEY, cli.run_admin

KEY = "mi_sk_test_0123456789abcdef"


@pytest.fixture
def setup_env(monkeypatch):
    """Deterministic env: no ambient key, and a stub `mi-mcp` binary path that
    exists so `doctor` (run at the end of setup) passes regardless of whether the
    console script is pip-installed (tests can run via `PYTHONPATH=src`)."""
    for v in ("MI_API_KEY", "MI_KEYCHAIN_ACCOUNT", "MI_MCP_OPT_IN_ALL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(cli, "_mi_mcp_bin", lambda: sys.executable)


def _mock_keychain_miss(monkeypatch):
    """Replace subprocess.run so `doctor`'s key lookup never touches the real
    Keychain — it 'misses', forcing resolution from the chmod-600 keyfile."""
    class _R:
        returncode = 1
        stdout = ""
        stderr = ""

    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: _R())


def _desktop(home):
    return home / "Library/Application Support/Claude/claude_desktop_config.json"


def _code(home):
    return home / ".claude.json"


def _wrapper(home):
    return home / ".memoryintelligence" / "mcp" / "run-mi-mcp.sh"


def _envfile(home):
    return home / ".memoryintelligence" / ".env"


def _optin(home):
    return home / ".memoryintelligence" / "mcp" / "opt-in-paths"


def test_setup_file_store_wires_and_opts_in(tmp_path, monkeypatch, setup_env):
    _mock_keychain_miss(monkeypatch)
    proj = tmp_path / "proj"
    proj.mkdir()
    rc = run_admin("setup", [
        "--home", str(tmp_path), "--surfaces", "desktop,code",
        "--store", "file", "--api-key", KEY, "--opt-in", str(proj),
    ])
    assert rc == 0

    # key landed in the chmod-600 keyfile
    envf = _envfile(tmp_path)
    assert envf.exists()
    assert f'MI_API_KEY="{KEY}"' in envf.read_text()
    assert stat.S_IMODE(envf.stat().st_mode) == 0o600

    # wrapper rendered + executable, and it RESOLVES the key (never embeds it)
    w = _wrapper(tmp_path)
    assert w.exists() and (w.stat().st_mode & 0o111)
    assert KEY not in w.read_text()

    # both surfaces wired with an empty env block
    for cfg_path in (_desktop(tmp_path), _code(tmp_path)):
        entry = json.loads(cfg_path.read_text())["mcpServers"][SERVER_KEY]
        assert entry["env"] == {}

    # capture opt-in recorded for the project dir
    assert os.path.realpath(str(proj)) in _optin(tmp_path).read_text()


def test_setup_writes_no_key_into_any_config(tmp_path, monkeypatch, setup_env):
    _mock_keychain_miss(monkeypatch)
    run_admin("setup", [
        "--home", str(tmp_path), "--surfaces", "desktop,code,cursor",
        "--store", "file", "--api-key", KEY, "--no-opt-in",
    ])
    # the ONLY file under HOME allowed to hold the key is the chmod-600 keyfile
    holders = [p for p in tmp_path.rglob("*")
               if p.is_file() and KEY in p.read_text(errors="ignore")]
    assert holders == [_envfile(tmp_path)]
    # and no JSON config holds it
    for p in tmp_path.rglob("*.json"):
        assert KEY not in p.read_text()


def test_setup_keychain_store_writes_no_file(tmp_path, monkeypatch, setup_env):
    calls: list[list[str]] = []

    class _R:
        returncode = 0
        stderr = ""

        def __init__(self, out=""):
            self.stdout = out

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if "add-generic-password" in cmd:
            return _R("")
        if "find-generic-password" in cmd:
            return _R(KEY)  # doctor resolves the just-stored key from the Keychain
        return _R("")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    rc = run_admin("setup", [
        "--home", str(tmp_path), "--surfaces", "desktop",
        "--store", "keychain", "--api-key", KEY, "--no-opt-in",
    ])
    assert rc == 0

    add = [c for c in calls if "add-generic-password" in c]
    assert add, "security add-generic-password was not called"
    assert "MI_API_KEY" in add[0] and KEY in add[0] and "-w" in add[0]

    # keychain path must NOT drop the key into a file anywhere
    assert not _envfile(tmp_path).exists()
    leaks = [p for p in tmp_path.rglob("*")
             if p.is_file() and KEY in p.read_text(errors="ignore")]
    assert leaks == []


def test_setup_opt_in_is_idempotent(tmp_path, monkeypatch, setup_env):
    _mock_keychain_miss(monkeypatch)
    proj = tmp_path / "proj"
    proj.mkdir()
    args = ["--home", str(tmp_path), "--surfaces", "desktop", "--store", "file",
            "--api-key", KEY, "--opt-in", str(proj)]
    run_admin("setup", args)
    run_admin("setup", args)
    lines = [ln for ln in _optin(tmp_path).read_text().splitlines() if ln.strip()]
    assert lines.count(os.path.realpath(str(proj))) == 1


def test_setup_no_opt_in_leaves_allowlist_absent(tmp_path, monkeypatch, setup_env):
    _mock_keychain_miss(monkeypatch)
    run_admin("setup", [
        "--home", str(tmp_path), "--surfaces", "desktop",
        "--store", "file", "--api-key", KEY, "--no-opt-in",
    ])
    assert not _optin(tmp_path).exists()


def test_init_alias_runs_setup(tmp_path, monkeypatch, setup_env):
    _mock_keychain_miss(monkeypatch)
    rc = run_admin("init", [
        "--home", str(tmp_path), "--surfaces", "desktop",
        "--store", "file", "--api-key", KEY, "--no-opt-in",
    ])
    assert rc == 0
    assert _envfile(tmp_path).exists()
    assert SERVER_KEY in json.loads(_desktop(tmp_path).read_text())["mcpServers"]


def test_setup_requires_key_when_noninteractive(tmp_path, monkeypatch, setup_env):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(""))  # isatty() → False
    rc = run_admin("setup", [
        "--home", str(tmp_path), "--store", "file", "--no-opt-in",
    ])
    assert rc == 2
    assert not _envfile(tmp_path).exists()  # nothing stored without a key


def test_setup_reads_key_from_env_when_noninteractive(tmp_path, monkeypatch, setup_env):
    # Safe non-interactive path: MI_API_KEY in the env (not in argv) is used when
    # there's no TTY and no --api-key flag.
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(""))  # isatty() → False
    monkeypatch.setenv("MI_API_KEY", KEY)
    rc = run_admin("setup", [
        "--home", str(tmp_path), "--surfaces", "desktop",
        "--store", "file", "--no-opt-in",  # note: no --api-key
    ])
    assert rc == 0
    assert f'MI_API_KEY="{KEY}"' in _envfile(tmp_path).read_text()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
