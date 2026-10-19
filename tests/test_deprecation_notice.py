"""#2186 — 0.2.14 is the final release; every entry point says so, on STDERR only.

The server speaks MCP (JSON-RPC) over stdout. A deprecation notice that leaked onto
stdout would break every host's framing, so these tests pin two things: the notice
appears, and stdout stays empty where stdout is the transport.
"""

from __future__ import annotations

import io
import sys

import pytest

import mi_mcp
import mi_mcp.__main__ as entry
import mi_mcp.cli as cli
from mi_mcp import DEPRECATION_NOTICE, warn_deprecated


def test_notice_names_version_replacement_and_issue():
    assert "0.2.14" in DEPRECATION_NOTICE
    assert "final release" in DEPRECATION_NOTICE
    assert "desktop app" in DEPRECATION_NOTICE
    assert "claude.ai" in DEPRECATION_NOTICE
    assert "issues/2186" in DEPRECATION_NOTICE
    assert mi_mcp.__version__ == "0.2.14", "the notice names a version the package is not"


def test_warn_deprecated_writes_to_stderr_by_default(capsys):
    warn_deprecated()
    captured = capsys.readouterr()
    assert DEPRECATION_NOTICE in captured.err
    assert captured.out == ""


def test_warn_deprecated_accepts_a_stream():
    buf = io.StringIO()
    warn_deprecated(buf)
    assert buf.getvalue().startswith("[mi-mcp] DEPRECATED: ")


def test_server_start_prints_notice_to_stderr_and_nothing_to_stdout(monkeypatch, capsys):
    """Bare `mi-mcp` (how the host spawns the server) warns before it touches config.

    Config loading is made to fail so the test never opens the stdio transport;
    the notice must already be on stderr by then, and stdout must be untouched.
    """
    from mi_mcp.config import MIConfig

    def _boom():
        raise ValueError("no key — stop here")

    monkeypatch.setattr(MIConfig, "from_env", staticmethod(_boom))
    monkeypatch.setattr(sys, "argv", ["mi-mcp"])
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert DEPRECATION_NOTICE in captured.err
    assert captured.out == "", "stdout is the MCP transport — nothing may be written there"


@pytest.mark.parametrize("command", ["setup", "doctor"])
def test_admin_commands_print_notice_before_help(command, capsys):
    """`--help` exits inside argparse, so a notice printed before parsing is the
    proof it comes first; it is on stderr, usage is on stdout as argparse intends."""
    with pytest.raises(SystemExit) as exc:
        cli.run_admin(command, ["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert DEPRECATION_NOTICE in captured.err
    assert f"mi-mcp {command}" in captured.out
