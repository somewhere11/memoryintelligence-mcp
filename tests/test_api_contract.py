"""MCP ↔ API contract tests.

Pins that every MIClient method sends only parameter *values the API accepts*, so
an API enum/type change can never silently 422 a real user. This is the general
form of the #260 bug: `explain` drifted boolean → enum and every agent call broke.

Self-contained: each test captures the payload a client method *would* send (no live
API, no network) and asserts every enum-constrained field is API-valid — and that a
boolean never reaches an enum field.

KEEP THE VALID_* SETS IN SYNC WITH THE API REQUEST MODELS (api/public/*.py). They
mirror the API enums on purpose: when the API changes an enum, the matching client +
these sets must change together, and this test failing is the drift alarm.
"""

from __future__ import annotations

import pytest

from mi_mcp.client import MIClient
from mi_mcp.config import MIConfig

# --- the API contract (mirror api/public/*.py request-model enums) -----------
VALID_EXPLAIN = {"none", "human", "audit", "full"}                  # /v1/memories/query, /v1/umo/match
VALID_PII = {"detect_only", "extract_and_redact", "hash", "reject"}  # /v1/process
VALID_RETENTION = {"meaning_only", "full", "summary_only"}          # /v1/process
VALID_SCOPE = {"user", "client", "project", "team", "org", "all"}    # all scoped ops


def _capturing_client():
    """An MIClient whose _request records the payload instead of hitting the network."""
    client = MIClient(MIConfig(api_key="test-key"))
    captured: dict = {}

    async def fake_request(method, path, *, json=None, params=None, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = json or {}
        captured["params"] = params or {}
        return {"status": "success", "data": {"results": []}}

    client._request = fake_request  # type: ignore[method-assign]
    return client, captured


# --- explain: the #260 bug class — bool must never reach the API; only the enum ---

@pytest.mark.asyncio
@pytest.mark.parametrize("explain", [True, False, "none", "human", "audit", "full"])
async def test_ask_explain_is_api_valid(explain):
    client, cap = _capturing_client()
    await client.ask("q", explain=explain)
    sent = cap["json"].get("explain")
    assert not isinstance(sent, bool), "explain must never reach the API as a boolean"
    assert sent is None or sent in VALID_EXPLAIN, f"ask() sent illegal explain={sent!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize("explain", sorted(VALID_EXPLAIN))
async def test_match_explain_is_api_valid(explain):
    client, cap = _capturing_client()
    await client.match("ulid_a", "ulid_b", explain=explain)
    sent = cap["json"]["explain"]
    assert not isinstance(sent, bool)
    assert sent in VALID_EXPLAIN, f"match() sent illegal explain={sent!r}"


# --- capture enums: pii_handling + retention_policy must be API-valid -----------

@pytest.mark.asyncio
@pytest.mark.parametrize("pii", sorted(VALID_PII))
async def test_capture_pii_handling_is_api_valid(pii):
    client, cap = _capturing_client()
    await client.capture("hello", pii_handling=pii)
    assert cap["json"]["pii_handling"] in VALID_PII


@pytest.mark.asyncio
@pytest.mark.parametrize("retention", sorted(VALID_RETENTION))
async def test_capture_retention_is_api_valid(retention):
    client, cap = _capturing_client()
    await client.capture("hello", retention_policy=retention)
    assert cap["json"]["retention_policy"] in VALID_RETENTION


@pytest.mark.asyncio
async def test_capture_config_defaults_are_api_valid():
    """The config defaults the client falls back to must themselves be API-valid —
    capture() always sends pii_handling + retention_policy, even when the caller
    passes neither, so a bad default would 422 every default capture."""
    client, cap = _capturing_client()
    await client.capture("hello")  # no pii/retention → uses config defaults
    assert cap["json"]["pii_handling"] in VALID_PII, "default pii_handling is not API-valid"
    assert cap["json"]["retention_policy"] in VALID_RETENTION, "default retention is not API-valid"


# --- scope: every scoped op must send an API-valid scope (or omit it) -----------

@pytest.mark.asyncio
@pytest.mark.parametrize("scope", sorted(VALID_SCOPE))
async def test_ask_scope_is_api_valid(scope):
    client, cap = _capturing_client()
    await client.ask("q", scope=scope)
    assert cap["json"]["scope"] in VALID_SCOPE


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", sorted(VALID_SCOPE))
async def test_capture_scope_is_api_valid(scope):
    client, cap = _capturing_client()
    await client.capture("hello", scope=scope)
    assert cap["json"]["scope"] in VALID_SCOPE


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", sorted(VALID_SCOPE))
async def test_list_scope_is_api_valid(scope):
    client, cap = _capturing_client()
    await client.list_memories(scope=scope)
    assert cap["params"]["scope"] in VALID_SCOPE
