"""Tests for MCP output shaping (P1-2).

The API returns a full envelope (`request_id`, `query_hash`, `meta`) wrapping
per-result objects that carry a score decomposition, entity arrays, and a
`content_text` that duplicates `summary`. The MCP must project this down to the
minimal agent-useful shape — `[{umo_id, summary, source, score}]` for ask,
a compact per-item shape for list — to cut recall tokens ~5x with no
capability loss (edge test T8). These tests pin that projection and prove the
untrusted-data wrapper still wraps the shaped payload.
"""

from __future__ import annotations

import json

import pytest

from mi_mcp.server import _fmt_untrusted, _shape_ask, _shape_list

# A realistic /v1/memories/query envelope (mirrors api/public/search.py).
_ASK_ENVELOPE = {
    "status": "success",
    "data": {
        "results": [
            {
                "umo_id": "11111111-1111-1111-1111-111111111111",
                "summary": "MI Proxy and MCP server are distinct layers.",
                "score": 0.79,
                "scores": {"semantic": 0.91, "keyword": 0.2, "entity": 0.0, "recency": 1.0},
                "entities": [{"text": "MCP", "type": "ORG", "polarity": None}],
                "created_at": "2026-06-16T00:00:00+00:00",
                "content_text": "MI Proxy and MCP server are distinct layers.",
                "truncated": False,
                "channel": "agent:mcp",
                "source": "mcp",
                "actor_type": "agent",
                "metadata": None,
            },
            {
                "umo_id": "22222222-2222-2222-2222-222222222222",
                "summary": "Tier 1/2/3 — reach out to warm prospects first.",
                "score": 0.54,
                "scores": {"semantic": 0.6, "keyword": 0.1, "entity": 0.0, "recency": 0.9},
                "entities": [],
                "created_at": "2026-06-15T00:00:00+00:00",
                "content_text": "Tier 1/2/3 — reach out to warm prospects first.",
                "truncated": False,
                "channel": "agent:mcp",
                "source": "mcp",
                "actor_type": "agent",
                "metadata": None,
            },
        ],
        "total_count": 2,
        "query_hash": "QU_deadbeef",
    },
    "request_id": "req_abc12345",
    "timestamp": "2026-06-18T00:00:00+00:00",
    "meta": {"score_formula": "semantic*0.6 + keyword*0.15 + entity*0.15 + recency*0.1"},
}

_LIST_ENVELOPE = {
    "status": "success",
    "data": {
        "items": [
            {
                "umo_id": "33333333-3333-3333-3333-333333333333",
                "summary": "Decided to use Postgres for billing.",
                "entities": [{"text": "Postgres", "type": "ORG"}],
                "topics": ["billing", "database"],
                "quality_score": 0.95,
                "source": "mcp",
                "created_at": "2026-06-14T00:00:00+00:00",
                "metadata": None,
            },
        ],
        "total_count": 162,
        "limit": 20,
        "offset": 0,
        "has_more": True,
    },
    "request_id": "req_def67890",
    "timestamp": "2026-06-18T00:00:00+00:00",
}

# Envelope-only fields an agent never needs — must NOT appear in the shaped JSON.
_ENVELOPE_FIELDS = (
    "request_id", "query_hash", "meta", "timestamp", "total_count",
    "scores", "content_text", "entities", "actor_type", "channel",
    "truncated", "quality_score", "has_more",
)


def test_shape_ask_keeps_only_the_agent_useful_fields():
    shaped = _shape_ask(_ASK_ENVELOPE)
    assert isinstance(shaped, list) and len(shaped) == 2
    for hit in shaped:
        assert set(hit) == {"umo_id", "summary", "source", "score"}
    assert shaped[0]["umo_id"] == "11111111-1111-1111-1111-111111111111"
    assert shaped[0]["summary"] == "MI Proxy and MCP server are distinct layers."
    assert shaped[0]["source"] == "mcp"
    assert shaped[0]["score"] == 0.79


def test_shape_ask_drops_the_envelope_and_per_result_noise():
    blob = json.dumps(_shape_ask(_ASK_ENVELOPE))
    for field in _ENVELOPE_FIELDS:
        assert field not in blob, f"{field!r} leaked into the shaped ask output"


def test_shape_ask_falls_back_to_content_text_when_summary_empty():
    env = json.loads(json.dumps(_ASK_ENVELOPE))
    env["data"]["results"][0]["summary"] = ""
    shaped = _shape_ask(env)
    # content_text is the only place the text survives — don't lose it.
    assert shaped[0]["summary"] == "MI Proxy and MCP server are distinct layers."


def test_shape_ask_is_a_large_token_reduction():
    raw = json.dumps(_ASK_ENVELOPE)
    shaped = json.dumps(_shape_ask(_ASK_ENVELOPE))
    # T8 target is ~5x; assert a conservative floor so the test isn't brittle.
    assert len(shaped) < len(raw) / 2


def test_shape_list_keeps_only_the_agent_useful_fields():
    shaped = _shape_list(_LIST_ENVELOPE)
    assert isinstance(shaped, list) and len(shaped) == 1
    assert set(shaped[0]) == {"umo_id", "summary", "source", "topics", "created_at"}
    assert shaped[0]["umo_id"] == "33333333-3333-3333-3333-333333333333"
    assert shaped[0]["source"] == "mcp"
    blob = json.dumps(shaped)
    for field in ("quality_score", "entities", "total_count", "has_more", "request_id"):
        assert field not in blob


def test_shapers_pass_through_unexpected_shapes_unchanged():
    # Error payloads / odd shapes must still surface to the agent verbatim.
    err = {"status": "error", "detail": "boom"}
    assert _shape_ask(err) is err
    assert _shape_list(err) is err
    assert _shape_ask("not a dict") == "not a dict"
    assert _shape_ask({"data": {}}) == {"data": {}}


# --- #482: `explain` must preserve the per-signal score decomposition ---
# The MCP shaper used to drop `scores` unconditionally, so `explain` had no
# observable effect through the tool. It is now kept iff explain was requested.

@pytest.mark.parametrize("level", ["human", "audit", "full", True])
def test_shape_ask_preserves_scores_when_explain_requested(level):
    shaped = _shape_ask(_ASK_ENVELOPE, explain=level)
    assert len(shaped) == 2
    for hit in shaped:
        assert set(hit) == {"umo_id", "summary", "source", "score", "scores"}
    assert shaped[0]["scores"] == {
        "semantic": 0.91, "keyword": 0.2, "entity": 0.0, "recency": 1.0,
    }


@pytest.mark.parametrize("explain", ["none", "false", False, "0", "None"])
def test_shape_ask_omits_scores_when_explain_off(explain):
    for hit in _shape_ask(_ASK_ENVELOPE, explain=explain):
        assert "scores" not in hit
    # default (no explain arg) also omits
    for hit in _shape_ask(_ASK_ENVELOPE):
        assert "scores" not in hit


def test_shape_ask_never_invents_scores_the_api_did_not_return():
    """If the API omitted `scores` (e.g. explain=none upstream), the shaper must
    not fabricate the key even when the caller passed explain."""
    env = json.loads(json.dumps(_ASK_ENVELOPE))
    for r in env["data"]["results"]:
        r.pop("scores", None)
    for hit in _shape_ask(env, explain="human"):
        assert "scores" not in hit


def test_untrusted_wrapper_still_wraps_the_shaped_payload():
    wrapped = _fmt_untrusted(_shape_ask(_ASK_ENVELOPE))
    assert "BEGIN UNTRUSTED DATA" in wrapped
    assert "END UNTRUSTED DATA" in wrapped
    # The shaped summary is present; the envelope noise is not.
    assert "MI Proxy and MCP server are distinct layers." in wrapped
    assert "query_hash" not in wrapped
