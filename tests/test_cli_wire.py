"""Tests for `mi-mcp wire/doctor/status` — all against temp HOME dirs.

Critical security assertion: no API key ("mi_sk_") is ever written into any
config file; the rendered wrapper carries the key-resolution logic instead.
"""

import json
from pathlib import Path

import mi_mcp.cli as cli

run_admin, SERVER_KEY = cli.run_admin, cli.SERVER_KEY


def _desktop(home: Path) -> Path:
    return home / "Library/Application Support/Claude/claude_desktop_config.json"


def _code(home: Path) -> Path:
    return home / ".claude.json"


def _wrapper(home: Path) -> Path:
    return home / ".mi" / "run-mi-mcp.sh"


def test_wire_creates_wrapper_and_configs_without_key(tmp_path):
    rc = run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop,code"])
    assert rc == 0

    wrapper = _wrapper(tmp_path)
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111  # executable
    body = wrapper.read_text()
    assert "exec " in body and "MI_API_KEY" in body
    assert "mi_sk_" not in body  # wrapper RESOLVES the key, never embeds it

    for cfg_path in (_desktop(tmp_path), _code(tmp_path)):
        cfg = json.loads(cfg_path.read_text())
        entry = cfg["mcpServers"][SERVER_KEY]
        assert entry["command"] == str(wrapper)
        assert entry["env"] == {}          # NO inline key
        assert "mi_sk_" not in cfg_path.read_text()


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


def test_status_reflects_wire(tmp_path, capsys):
    run_admin("wire", ["--home", str(tmp_path), "--surfaces", "desktop"])
    capsys.readouterr()  # clear
    run_admin("status", ["--home", str(tmp_path)])
    out = capsys.readouterr().out
    assert "wired ✓" in out
    assert "desktop" in out


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
