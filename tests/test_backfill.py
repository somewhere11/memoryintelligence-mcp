"""Tests for the backfill export-stream analysis (mi-mcp backfill --dry-run)."""

import json

from mi_mcp.cli import _analyze_export


def _line(d):
    return json.dumps(d)


def test_counts_umos_and_raw_text():
    lines = [_line({"id": "1", "raw_text": "hello"}), _line({"id": "2", "summary": "x"})]
    st = _analyze_export(lines)
    assert st.total == 2
    assert st.with_raw == 1
    assert st.approx_bytes > 0


def test_flags_content_redacted_at_ingest():
    lines = [
        _line({"id": "1", "raw_text": "<PERSON> was absent"}),
        _line({"id": "2", "raw_text": "clean note about lunch"}),
    ]
    st = _analyze_export(lines)
    assert st.total == 2
    assert st.redacted_at_source == 1


def test_stream_error_sentinel_is_captured_not_counted():
    lines = [_line({"id": "1"}), _line({"_error": "Export interrupted", "cursor": "abc"})]
    st = _analyze_export(lines)
    assert st.total == 1
    assert st.stream_error == "Export interrupted"


def test_blank_and_malformed_lines_are_skipped():
    lines = ["", "   ", "not json at all", _line({"id": "1"})]
    st = _analyze_export(lines)
    assert st.total == 1


def test_empty_stream():
    st = _analyze_export([])
    assert st.total == 0
    assert st.redacted_at_source == 0
    assert st.stream_error is None
