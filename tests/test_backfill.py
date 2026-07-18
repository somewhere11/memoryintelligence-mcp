"""Tests for the backfill export-stream analysis (mi-mcp backfill --dry-run)."""

import json

from mi_mcp.cli import (
    _analyze_export,
    _parse_export_objects,
    _payload_for_umo,
    _public_metadata_for_umo,
    _text_for_embedding,
)


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


# --- --execute transform helpers (pure; no network, no model) --------------

def test_parse_export_objects_skips_errors_and_junk():
    lines = [
        _line({"id": "1", "summary": "a"}),
        "",
        "not json",
        _line({"_error": "interrupted", "cursor": "x"}),
        _line({"id": "2", "summary": "b"}),
    ]
    objs = _parse_export_objects(lines)
    assert [o["id"] for o in objs] == ["1", "2"]


def test_text_for_embedding_prefers_normalized_then_raw_then_summary():
    assert _text_for_embedding({"normalized_text": "n", "raw_text": "r", "summary": "s"}) == "n"
    assert _text_for_embedding({"raw_text": "r", "summary": "s"}) == "r"
    assert _text_for_embedding({"summary": "s"}) == "s"
    assert _text_for_embedding({"summary": "   "}) == ""
    assert _text_for_embedding({}) == ""


def test_payload_carries_index_fields_and_origin():
    row = {
        "id": "u1", "summary": "sum", "entities": [{"text": "Bob"}],
        "tags": ["work"], "created_at": "2026-06-20T00:00:00Z",
        "normalized_text": "norm", "semantic_hash": "h",
    }
    p = _payload_for_umo(row, [0.1, 0.2])
    assert p["embedding"] == [0.1, 0.2]
    assert p["summary"] == "sum"
    assert p["entities"] == [{"text": "Bob"}]
    assert p["topics"] == ["work"]
    assert p["origin"] == "backfill"


def test_public_metadata_is_plaintext_safe_and_desktop_compatible():
    pm = _public_metadata_for_umo(
        {"id": "u1", "created_at": "t", "schema_version": "1.0.0"}, "did:mi:owner-local"
    )
    assert pm["umo_id"] == "u1"
    assert pm["created_at"] == "t"
    assert pm["owner_did"] == "did:mi:owner-local"
    assert pm["origin"] == "backfill"
    # desktop-compatible field set (so the desktop app reads MCP-written files)
    assert pm["content_type"] == "text/plain"
    assert pm["format_version"] == "0x0100"
    assert pm["mi_key_id"] == "local"
    assert pm["schema_version"] == "1.0.0"
    assert pm["source_count"] == 1
    # no PII (summary/entities/raw text) leaks into plaintext metadata
    assert "summary" not in pm and "entities" not in pm and "normalized_text" not in pm
