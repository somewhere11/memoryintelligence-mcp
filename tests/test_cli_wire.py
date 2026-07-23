"""Tests for `mi-mcp wire/doctor/status` — all against temp HOME dirs.

Critical security assertion: no API key ("mi_sk_") is ever written into any
config file; Keychain resolution carries the key instead (wrapper for Code/Cursor,
in-process for the direct-interpreter Desktop entry).
"""

import json
import sys
from pathlib import Path

import mi_mcp.cli as cli

run_admin, SERVER_KEY = cli.run_admin, cli.SERVER_KEY


def _desktop(home: Path) -> Path:
    return home / "Library/Application Support/Claude/claude_desktop_config.json"


def _code(home: Path) -> Path:
    return home / ".claude.json"


def _wrapper(home: Path) -> Path:
    return home / ".memoryintelligence" / "mcp" / "run-mi-mcp.sh"


def test_wire_creates_wrapper_and_configs_without_key(tmp_path):
    rc = run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop,code"])
    assert rc == 0

    wrapper = _wrapper(tmp_path)
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111  # executable
    body = wrapper.read_text()
    assert "exec " in body and "MI_API_KEY" in body
    assert "mi_sk_" not in body  # wrapper RESOLVES the key, never embeds it

    # Code/Cursor aren't sandboxed like Claude Desktop → keep the self-healing wrapper.
    code_entry = json.loads(_code(tmp_path).read_text())["mcpServers"][SERVER_KEY]
    assert code_entry["command"] == str(wrapper)
    assert code_entry["env"] == {}          # NO inline key
    assert "mi_sk_" not in _code(tmp_path).read_text()

    # Desktop (P0): macOS Claude Desktop's sandbox blocks the shell wrapper, so wire spawns
    # the Python interpreter directly (a real binary the sandbox allows). The key still isn't
    # in the file (resolved from the Keychain at launch); MI_VAULT names the one vault (D7).
    d_entry = json.loads(_desktop(tmp_path).read_text())["mcpServers"][SERVER_KEY]
    assert d_entry["command"] == sys.executable
    assert d_entry["args"] == ["-m", "mi_mcp"]
    assert not str(d_entry["command"]).endswith(".sh")   # never a sandbox-blocked shell script
    assert d_entry["env"].get("MI_VAULT", "").endswith("/Somewhere")
    assert "mi_sk_" not in _desktop(tmp_path).read_text()


def test_wire_vscode_uses_servers_key_and_stdio_type(tmp_path):
    """VS Code / Copilot read a different schema than Claude: the server map is
    under "servers" (not "mcpServers"), and each entry needs an explicit
    "type": "stdio". Same wrapper, still no key written to the file."""
    rc = run_admin("wire", ["--home", str(tmp_path), "--surfaces", "vscode"])
    assert rc == 0
    p = tmp_path / "Library/Application Support/Code/User/mcp.json"
    cfg = json.loads(p.read_text())
    assert "servers" in cfg and "mcpServers" not in cfg
    entry = cfg["servers"][SERVER_KEY]
    assert entry["type"] == "stdio"
    assert entry["command"] == str(_wrapper(tmp_path))
    assert entry["env"] == {}              # NO inline key
    assert "mi_sk_" not in p.read_text()


def test_wrapper_self_heals_when_baked_path_is_stale(tmp_path):
    # Guard against the idea-vault failure mode: a config pointing at a single
    # absolute path that later goes missing → silent spawn failure on every
    # launch. The wrapper must try the wire-time path, then re-resolve via PATH
    # and the common install dirs, then exit with one actionable error.
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    body = _wrapper(tmp_path).read_text()
    assert "command -v mi-mcp" in body                       # PATH fallback
    assert "$HOME/.local/bin/mi-mcp" in body                 # common install dir
    assert "pip install -U memoryintelligence-mcp" in body   # actionable recovery
    assert 'exec "$MI_MCP_BIN"' in body                      # execs the resolved bin
    assert "mi_sk_" not in body                              # still never embeds the key


def test_wrapper_sets_mi_vault_to_somewhere_behind_a_guard(tmp_path):
    # #653: the wrapper must point the local .umo vault at the Desktop vault
    # (~/Somewhere) so both surfaces resolve ONE vault — but only as a DEFAULT,
    # behind a guard so an explicit MI_VAULT (env or config) still wins.
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    body = _wrapper(tmp_path).read_text()
    assert 'export MI_VAULT="$HOME/Somewhere"' in body   # points at the Desktop vault
    assert '[[ -z "${MI_VAULT:-}" ]]' in body            # only when unset — user's value wins
    assert "mi_sk_" not in body                          # still never a key


def test_doctor_vault_check_green_once_wired(tmp_path, capsys, monkeypatch):
    # After wire bakes MI_VAULT=~/Somewhere into the wrapper, doctor's vault-path
    # check must read that wired default and go green — even though MI_VAULT is not
    # set in the shell running doctor.
    monkeypatch.delenv("MI_VAULT", raising=False)
    # Before wire: the default resolves to ~/MemoryIntelligence → mismatch (warns).
    run_admin("doctor", ["--home", str(tmp_path)])
    before = capsys.readouterr().out
    assert "vault path" in before
    assert "#653" in before                              # flags the mismatch pre-wire

    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    capsys.readouterr()  # clear
    run_admin("doctor", ["--home", str(tmp_path)])
    after = capsys.readouterr().out
    # Green: resolves to the Desktop vault via the wired wrapper, no #653 warning.
    assert str(tmp_path / "Somewhere") in after
    assert "wrapper (wired)" in after
    assert "#653" not in after


def test_doctor_vault_check_respects_explicit_mi_vault(tmp_path, capsys, monkeypatch):
    # An explicit MI_VAULT the user set is their choice and must pass doctor even
    # if it isn't ~/Somewhere (we surface the path, we don't second-guess it).
    custom = tmp_path / "my-own-vault"
    monkeypatch.setenv("MI_VAULT", str(custom))
    run_admin("doctor", ["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert str(custom) in out
    assert "MI_VAULT env" in out
    assert "#653" not in out       # user's explicit choice → no nag


def test_capture_anywhere_sets_desktop_env_only(tmp_path):
    # --capture-anywhere opts capture in for Claude Desktop (no project cwd to
    # scope to) but must NOT touch Cursor, which opens a real folder and keeps
    # per-folder consent. And it is still never a key.
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop,cursor",
                       "--capture-anywhere"])
    desktop = json.loads(_desktop(tmp_path).read_text())["mcpServers"][SERVER_KEY]
    cursor = json.loads((tmp_path / ".cursor/mcp.json").read_text())["mcpServers"][SERVER_KEY]
    # desktop opted in + provenance-tagged so captures are reviewable apart from projects
    assert desktop["env"]["MI_MCP_OPT_IN_ALL"] == "1"
    assert desktop["env"]["MI_DEFAULT_SOURCE"] == "claude-desktop"
    assert desktop["env"]["MI_VAULT"].endswith("/Somewhere")   # one-vault (D7) rides along
    assert cursor["env"] == {}                            # cursor keeps consent (uses wrapper)
    assert "mi_sk_" not in _desktop(tmp_path).read_text()  # still no key


def test_capture_anywhere_preserved_on_plain_rewire(tmp_path):
    # Once set, a later plain `wire` (no flag) must NOT silently disable it —
    # otherwise an upgrade/re-wire would quietly turn capture back off.
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop", "--capture-anywhere"])
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])  # no flag
    desktop = json.loads(_desktop(tmp_path).read_text())["mcpServers"][SERVER_KEY]
    assert desktop["env"].get("MI_MCP_OPT_IN_ALL") == "1"   # preserved (alongside MI_VAULT)


def test_no_capture_anywhere_turns_it_off(tmp_path):
    # The reversible half of the toggle: --no-capture-anywhere explicitly disables
    # a previously-set desktop opt-in (distinct from a plain re-wire, which preserves).
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop", "--capture-anywhere"])
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop", "--no-capture-anywhere"])
    desktop = json.loads(_desktop(tmp_path).read_text())["mcpServers"][SERVER_KEY]
    assert "MI_MCP_OPT_IN_ALL" not in desktop["env"]   # opt-in off (MI_VAULT still set)


def test_wire_default_leaves_capture_gate_on(tmp_path):
    # Default (no flag) must NOT bypass the consent gate — explicit opt-in is the
    # ownership stance. Desktop env stays empty.
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    desktop = json.loads(_desktop(tmp_path).read_text())["mcpServers"][SERVER_KEY]
    assert "MI_MCP_OPT_IN_ALL" not in desktop["env"]   # consent gate on; MI_VAULT still set


def test_wire_writes_zero_keys_anywhere(tmp_path):
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop,code,cursor"])
    # scan every file under the temp home for a key leak
    leaks = [
        p for p in tmp_path.rglob("*")
        if p.is_file() and "mi_sk_" in p.read_text(errors="ignore")
    ]
    assert leaks == []


def test_wire_dry_run_writes_nothing(tmp_path):
    rc = run_admin("wire", ["--home", str(tmp_path), "--dry-run"])
    assert rc == 0
    assert not _wrapper(tmp_path).exists()
    assert not _desktop(tmp_path).exists()
    assert list(tmp_path.rglob("*.json")) == []


def test_wire_is_idempotent(tmp_path):
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    first = _desktop(tmp_path).read_text()
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    assert _desktop(tmp_path).read_text() == first


def test_wire_preserves_other_servers(tmp_path):
    cfg_path = _desktop(tmp_path)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"mcpServers": {"other": {"command": "/usr/bin/other"}}}))
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    cfg = json.loads(cfg_path.read_text())
    assert cfg["mcpServers"]["other"] == {"command": "/usr/bin/other"}  # untouched
    assert SERVER_KEY in cfg["mcpServers"]                              # ours added


def test_wire_migrates_legacy_server_id(tmp_path):
    # A pre-0.1.8 config registered under the old id "memory-intelligence" is
    # replaced by the new "memoryintelligence" id on wire — no orphan/duplicate.
    cfg_path = _desktop(tmp_path)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"mcpServers": {
        "memory-intelligence": {"command": "/old/run-mi-mcp.sh", "args": [], "env": {}},
        "other": {"command": "/usr/bin/other"},
    }}))
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    servers = json.loads(cfg_path.read_text())["mcpServers"]
    assert "memory-intelligence" not in servers                # legacy id removed
    assert SERVER_KEY in servers                                # new id added
    assert servers["other"] == {"command": "/usr/bin/other"}   # unrelated untouched


def test_status_reflects_wire(tmp_path, capsys):
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    capsys.readouterr()  # clear
    run_admin("status", ["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert "wired ✓" in out
    assert "desktop" in out


def test_wire_migrates_legacy_opt_in_forward(tmp_path):
    # An existing ~/.mi/opt-in-paths (≤0.1.6 install) is copied to the new
    # ~/.memoryintelligence/mcp/ location on wire, non-destructively.
    legacy = tmp_path / ".mi" / "opt-in-paths"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("/some/legacy/project\n")

    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])

    new = tmp_path / ".memoryintelligence" / "mcp" / "opt-in-paths"
    assert new.exists(), "legacy opt-in not migrated to the new location"
    assert "/some/legacy/project" in new.read_text()
    assert legacy.exists(), "migration must be non-destructive (legacy left intact)"


def test_wire_uses_on_brand_dir_not_legacy(tmp_path):
    # The launcher + opt-in must land under ~/.memoryintelligence/, never ~/.mi/.
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    assert (tmp_path / ".memoryintelligence" / "mcp" / "run-mi-mcp.sh").exists()
    assert not (tmp_path / ".mi").exists(), "must not create the legacy ~/.mi dir"


def test_wire_code_uses_claude_cli_for_real_home(tmp_path, monkeypatch):
    # Make tmp_path look like the real HOME so the claude-CLI branch activates.
    monkeypatch.setenv("HOME", str(tmp_path))

    calls: list[list[str]] = []
    monkeypatch.setattr(cli.shutil, "which",
                        lambda name: "/fake/claude" if name == "claude" else f"/fake/{name}")

    class _R:
        returncode = 0
        stderr = ""
        stdout = ""

    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: (calls.append(cmd), _R())[1])

    cli.run_admin("wire", ["--home", str(tmp_path), "--surfaces", "code"])

    add_calls = [c for c in calls if "add" in c]
    assert add_calls, "claude mcp add was not called"
    assert SERVER_KEY in add_calls[0]
    assert "-s" in add_calls[0] and "user" in add_calls[0]
    assert not (tmp_path / ".claude.json").exists()  # no hand-edit of the live file


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])


# ── #1135: doctor catches the sandbox-blocked Desktop entry ──────────────────
# Claude Desktop's macOS sandbox refuses to exec shell scripts, so a Desktop
# entry pointing at run-mi-mcp.sh (written by wire <= published 0.2.2) starts,
# never completes the handshake, and dies at the host's 60s timeout — while
# doctor showed green. These pin the check that turns that into one red line.

def test_doctor_fails_on_shell_script_desktop_entry(tmp_path, capsys):
    cfg = _desktop(tmp_path)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"mcpServers": {SERVER_KEY: {
        "command": str(tmp_path / ".memoryintelligence/mcp/run-mi-mcp.sh"),
        "args": [], "env": {},
    }}}))
    rc = run_admin("doctor", ["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc != 0
    assert "[✗] desktop entry sandbox-launchable" in out
    # the remediation must be printed in place — the whole point of the check —
    # and must carry the env block: a manual edit that drops MI_VAULT launches
    # fine but reads the wrong vault, invisibly to doctor's vault check
    assert "-m" in out and "mi_mcp" in out
    assert "MI_VAULT" in out and "Somewhere" in out


def test_doctor_passes_direct_python_desktop_entry(tmp_path, capsys):
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    capsys.readouterr()  # clear wire output
    run_admin("doctor", ["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert "[✓] desktop entry sandbox-launchable" in out


def test_doctor_skips_launchable_check_when_desktop_unwired(tmp_path, capsys):
    run_admin("doctor", ["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert "sandbox-launchable" not in out


def test_doctor_fails_on_empty_desktop_command(tmp_path, capsys):
    # "" does not end with ".sh" — an absent command must not read as green.
    cfg = _desktop(tmp_path)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"mcpServers": {SERVER_KEY: {"args": ["-m", "mi_mcp"]}}}))
    rc = run_admin("doctor", ["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc != 0
    assert "[✗] desktop entry sandbox-launchable" in out
    assert "no command" in out
