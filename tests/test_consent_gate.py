"""Unit tests for the capture consent gate (Story 8).

Pure-function tests for mi_mcp.config.is_cwd_opted_in / load_opt_in_paths —
no server, no network.
"""

import pytest

from mi_mcp.config import is_cwd_opted_in, load_opt_in_paths


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
