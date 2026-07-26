"""Unit tests for the capture consent gate (Story 8).

Pure-function tests for mi_mcp.config.is_cwd_opted_in / load_opt_in_paths —
no server, no network.
"""

import pytest

from mi_mcp.config import (
    capture_gate,
    cwd_has_project_context,
    is_cwd_opted_in,
    load_opt_in_paths,
)


def test_empty_allowlist_denies(monkeypatch):
    monkeypatch.delenv("MI_MCP_OPT_IN_ALL", raising=False)
    assert is_cwd_opted_in("/tmp/anything", patterns=[]) is False


def test_exact_dir_matches(monkeypatch):
    monkeypatch.delenv("MI_MCP_OPT_IN_ALL", raising=False)
    assert is_cwd_opted_in("/Users/x/proj", patterns=["/Users/x/proj"]) is True


def test_subdir_matches(monkeypatch):
    monkeypatch.delenv("MI_MCP_OPT_IN_ALL", raising=False)
    assert is_cwd_opted_in("/Users/x/proj/sub/deep", patterns=["/Users/x/proj"]) is True


def test_sibling_prefix_does_not_match(monkeypatch):
    # /Users/x/project must NOT match allowlisted /Users/x/proj (string-prefix trap)
    monkeypatch.delenv("MI_MCP_OPT_IN_ALL", raising=False)
    assert is_cwd_opted_in("/Users/x/project", patterns=["/Users/x/proj"]) is False


def test_glob_matches(monkeypatch):
    monkeypatch.delenv("MI_MCP_OPT_IN_ALL", raising=False)
    assert is_cwd_opted_in("/Users/x/world/alpha", patterns=["/Users/x/world/*"]) is True


def test_opt_in_all_bypasses(monkeypatch):
    monkeypatch.setenv("MI_MCP_OPT_IN_ALL", "1")
    assert is_cwd_opted_in("/anywhere", patterns=[]) is True


def test_load_parses_comments_blanks_and_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    f = tmp_path / "opt-in-paths"
    f.write_text("# a comment\n\n~/proj\n/abs/path\n")
    out = load_opt_in_paths(f)
    assert str(tmp_path / "proj") in out  # ~ expanded
    assert "/abs/path" in out
    assert all(not x.startswith("#") for x in out)
    assert "" not in out


def test_load_absent_file_returns_empty(tmp_path):
    assert load_opt_in_paths(tmp_path / "does-not-exist") == []


# --- capture_gate: the no-project-cwd surface-level consent (GUI/remote) --------

@pytest.fixture
def _clean_env(monkeypatch):
    monkeypatch.delenv("MI_MCP_OPT_IN_ALL", raising=False)
    monkeypatch.delenv("MI_MCP_STRICT_CWD", raising=False)


def test_project_context_detection(_clean_env):
    # the filesystem root has no project context; a real folder does
    assert cwd_has_project_context("/") is False
    assert cwd_has_project_context("/Users/x/proj") is True


def test_gate_allows_root_cwd_with_connector_tag(_clean_env):
    # The Griffen/claude.ai case: server spawned at "/", nothing opted in.
    # Folder consent can't apply → allow, tagged as connector-origin.
    allowed, source = capture_gate(cwd="/", patterns=[])
    assert allowed is True
    assert source == "claude-connector"


def test_gate_blocks_real_folder_not_opted_in(_clean_env):
    # A genuine project folder that isn't on the allowlist is still blocked,
    # with no source tag — the per-folder model is intact where it has signal.
    allowed, source = capture_gate(cwd="/Users/x/proj", patterns=[])
    assert allowed is False
    assert source is None


def test_gate_allows_opted_in_folder_without_tag(_clean_env):
    allowed, source = capture_gate(cwd="/Users/x/proj/sub", patterns=["/Users/x/proj"])
    assert allowed is True
    assert source is None  # caller's own source/default is used, not the connector tag


def test_strict_mode_blocks_root_cwd(monkeypatch):
    # MI_MCP_STRICT_CWD=1 opts back into strict folder gating even at "/".
    monkeypatch.delenv("MI_MCP_OPT_IN_ALL", raising=False)
    monkeypatch.setenv("MI_MCP_STRICT_CWD", "1")
    allowed, source = capture_gate(cwd="/", patterns=[])
    assert allowed is False
    assert source is None


def test_opt_in_all_still_wins_over_everything(monkeypatch):
    monkeypatch.setenv("MI_MCP_OPT_IN_ALL", "1")
    monkeypatch.delenv("MI_MCP_STRICT_CWD", raising=False)
    allowed, source = capture_gate(cwd="/Users/x/proj", patterns=[])
    assert allowed is True
    assert source is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
