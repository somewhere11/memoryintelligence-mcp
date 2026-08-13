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

    # code keeps the wrapper + empty env; desktop is the direct-interpreter entry that
    # carries MI_VAULT (D7) — neither embeds a key.
    assert json.loads(_code(tmp_path).read_text())["mcpServers"][SERVER_KEY]["env"] == {}
    d_env = json.loads(_desktop(tmp_path).read_text())["mcpServers"][SERVER_KEY]["env"]
    assert d_env.get("MI_VAULT", "").endswith("/Somewhere")
    assert "MI_MCP_OPT_IN_ALL" not in d_env  # this test opts in a PROJECT, not desktop-wide

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
    # #1351: "no key" now has to mean no key ANYWHERE, including the Keychain —
    # setup consults stored credentials before prompting, so without this stub
    # the test would read the developer's real key off the host and pass or
    # fail depending on whose machine it ran on.
    _mock_keychain_miss(monkeypatch)
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


# =============================================================================
# #1351 — re-running `setup` must not destroy a working key
# =============================================================================
#
# `setup` is the most discoverable command for "my install is broken, fix it",
# but it was written as the FIRST-RUN path and prompted for the key
# unconditionally. A returning user got sent to the portal to dig out a
# credential they never needed to touch, and a perfectly good stored key was
# overwritten. `mi-mcp wire` is the right command for that user — it
# re-connects the hosts and never touches the key — and nothing said so.

OLD_KEY = "mi_sk_test_existing_0123456789"
NEW_KEY = "mi_sk_test_replacement_9876543"


def _seed_keyfile(home, key):
    """Put a key on disk the way a previous `setup --store file` would have."""
    envf = _envfile(home)
    envf.parent.mkdir(parents=True, exist_ok=True)
    envf.write_text(f'MI_API_KEY="{key}"\n')
    envf.chmod(0o600)
    return envf


class TestSetupKeepsAnExistingKey:
    def test_rerun_without_a_key_keeps_the_stored_one(
        self, tmp_path, monkeypatch, setup_env
    ):
        """The defect: a re-run used to demand the key again and overwrite it."""
        _mock_keychain_miss(monkeypatch)
        _seed_keyfile(tmp_path, OLD_KEY)

        # No --api-key, no MI_API_KEY, and NOT a tty. Before the fix this path
        # errored with "no API key" (exit 2) rather than using what was there.
        monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False, raising=False)

        rc = run_admin("setup", [
            "--home", str(tmp_path), "--surfaces", "code",
            "--store", "file", "--no-opt-in",
        ])
        assert rc == 0, "a re-run with a key already stored must just work"
        assert f'MI_API_KEY="{OLD_KEY}"' in _envfile(tmp_path).read_text()

    def test_reset_key_flag_still_replaces_it(
        self, tmp_path, monkeypatch, setup_env
    ):
        """Keeping the key must not make replacing it impossible."""
        _mock_keychain_miss(monkeypatch)
        _seed_keyfile(tmp_path, OLD_KEY)

        rc = run_admin("setup", [
            "--home", str(tmp_path), "--surfaces", "code", "--store", "file",
            "--no-opt-in", "--reset-key", "--api-key", NEW_KEY,
        ])
        assert rc == 0
        assert f'MI_API_KEY="{NEW_KEY}"' in _envfile(tmp_path).read_text()

    def test_an_explicit_key_still_wins_without_reset(
        self, tmp_path, monkeypatch, setup_env
    ):
        """Passing --api-key is an unambiguous instruction; honour it."""
        _mock_keychain_miss(monkeypatch)
        _seed_keyfile(tmp_path, OLD_KEY)

        rc = run_admin("setup", [
            "--home", str(tmp_path), "--surfaces", "code", "--store", "file",
            "--no-opt-in", "--api-key", NEW_KEY,
        ])
        assert rc == 0
        assert f'MI_API_KEY="{NEW_KEY}"' in _envfile(tmp_path).read_text()

    def test_the_kept_key_is_never_printed_in_full(
        self, tmp_path, monkeypatch, setup_env, capsys
    ):
        _mock_keychain_miss(monkeypatch)
        _seed_keyfile(tmp_path, OLD_KEY)
        monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False, raising=False)

        run_admin("setup", [
            "--home", str(tmp_path), "--surfaces", "code",
            "--store", "file", "--no-opt-in",
        ])
        out = capsys.readouterr()
        combined = out.out + out.err
        assert OLD_KEY not in combined, "setup echoed the secret"

        # ⚠️ NOTHING DERIVED FROM THE KEY, not merely "not the whole key".
        #
        # This test used to accept `mi_sk_test_…` — a `key[:11]…key[-4:]` mask —
        # as proof of masking, so it would have PASSED on the leak it existed to
        # prevent. CodeQL flagged that line as clear-text logging of sensitive
        # information (high). Replacing the mask with a SHA-256 fingerprint did
        # not help: CodeQL taints the key value, so the hash was still a logging
        # flow AND added a second alert for weak hashing of sensitive data.
        #
        # The resolution is that nothing key-derived is printed at all. What the
        # user needs is that a key was kept and WHERE — neither requires any part
        # of the secret.
        secret = OLD_KEY.split("_", 3)[-1]          # the part after mi_sk_<env>_
        assert secret[-4:] not in combined, "a tail of the secret was printed"
        assert secret[:6] not in combined, "a head of the secret was printed"

        import hashlib

        assert hashlib.sha256(OLD_KEY.encode()).hexdigest()[:8] not in combined, (
            "a hash of the key was printed — still a derived-secret flow"
        )
        # …and the useful half survives: that a key was kept.
        assert "keeping the key already stored" in out.out

    def test_output_points_at_wire_as_the_narrower_command(
        self, tmp_path, monkeypatch, setup_env, capsys
    ):
        """The discoverability half of the bug, not just the destructive half."""
        _mock_keychain_miss(monkeypatch)
        _seed_keyfile(tmp_path, OLD_KEY)
        monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False, raising=False)

        run_admin("setup", [
            "--home", str(tmp_path), "--surfaces", "code",
            "--store", "file", "--no-opt-in",
        ])
        assert "mi-mcp wire" in capsys.readouterr().out, (
            "a user who reached for `setup` because something broke should be "
            "told which command they actually wanted"
        )


def test_stored_key_lookup_ignores_the_environment(tmp_path, monkeypatch):
    """`_stored_api_key` answers "what would I overwrite?", not "what resolves?".

    `config.resolve_api_key` consults MI_API_KEY from the environment. Setup
    must not: an env var is neither stored nor overwritten, so reporting it as
    "already stored" would be a claim the user cannot act on.
    """
    _mock_keychain_miss(monkeypatch)
    monkeypatch.setenv("MI_API_KEY", "mi_sk_test_from_the_environment")
    assert cli._stored_api_key(tmp_path) is None


def test_env_var_outranks_a_stored_key(tmp_path, monkeypatch, setup_env):
    """Precedence: --api-key → MI_API_KEY → stored → prompt.

    Setting MI_API_KEY for one invocation is a deliberate per-run override; a
    key sitting on disk must not shadow it. The reverse order would make
    `MI_API_KEY=… mi-mcp setup` a silent no-op on any machine already set up.
    """
    _mock_keychain_miss(monkeypatch)
    _seed_keyfile(tmp_path, OLD_KEY)
    monkeypatch.setenv("MI_API_KEY", NEW_KEY)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False, raising=False)

    rc = run_admin("setup", [
        "--home", str(tmp_path), "--surfaces", "code",
        "--store", "file", "--no-opt-in",
    ])
    assert rc == 0
    assert f'MI_API_KEY="{NEW_KEY}"' in _envfile(tmp_path).read_text()
