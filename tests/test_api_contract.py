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

    async def fake_request(method, path, *, json=None, params=None, headers=None, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = json  # no coercion — None must stay distinguishable from {}
        captured["params"] = params or {}
        captured["headers"] = headers  # None must stay distinguishable from {}
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


# --- workspaces (#1320): a bare GET with no params, same endpoint as the remote ---

@pytest.mark.asyncio
async def test_workspaces_request_shape():
    """mi_workspaces takes no input — the client must send a plain
    GET /v1/workspaces with no body and no params (the API derives the caller
    from the key). Pins the path the remote MCP surface also calls, so both
    surfaces stay answer-identical."""
    client, cap = _capturing_client()
    await client.workspaces()
    assert cap["method"] == "GET"
    assert cap["path"] == "/v1/workspaces"
    assert cap["json"] is None   # genuinely NO body (helper no longer coerces None → {})
    assert cap["params"] == {}


# --- workspace routing on capture (#385 UC1) --------------------------------
# The workspace target travels as a HEADER, not a body field. Two header names
# exist for the one concept and the honored one depends on the auth plane
# (X-MI-Workspace = API-key plane, which is what this package uses;
# X-Workspace-Id = JWT plane, what the remote MCP sends), so the client sends
# both. These pin that, because a routing header that silently stops being sent
# looks exactly like a working capture — it just lands in the wrong workspace.

@pytest.mark.asyncio
async def test_capture_sends_both_workspace_routing_headers():
    client, cap = _capturing_client()
    await client.capture("hello", workspace_id="01JWORKSPACEULID0000000000")
    headers = cap["headers"] or {}
    assert headers.get("X-MI-Workspace") == "01JWORKSPACEULID0000000000", (
        "API-key plane header missing — deps.py::get_api_key reads X-MI-Workspace; "
        "without it the capture silently lands in the caller's home workspace"
    )
    assert headers.get("X-Workspace-Id") == "01JWORKSPACEULID0000000000", (
        "JWT-plane header missing — deps.py::get_api_key_or_jwt reads X-Workspace-Id"
    )


@pytest.mark.asyncio
async def test_capture_workspace_id_is_not_a_body_field():
    """workspace_id must NOT leak into the /v1/process body: the API has no such
    request-model field, and `scope_id` (which IS a body field) is a different
    axis entirely. Sending it in the body would be a silent no-op."""
    client, cap = _capturing_client()
    await client.capture("hello", workspace_id="01JWORKSPACEULID0000000000")
    assert "workspace_id" not in cap["json"]


@pytest.mark.asyncio
async def test_capture_without_workspace_sends_no_routing_headers():
    """Personal is the default: an untargeted capture must send no routing header
    at all, so the server's own home-binding decides where it lands."""
    client, cap = _capturing_client()
    await client.capture("hello")
    assert cap["headers"] is None


@pytest.mark.asyncio
async def test_ask_sends_workspace_routing_headers():
    """#385 UC2 — the read side routes by the same headers as capture."""
    client, cap = _capturing_client()
    await client.ask("q", workspace_id="01JWORKSPACEULID0000000000")
    headers = cap["headers"] or {}
    assert headers.get("X-MI-Workspace") == "01JWORKSPACEULID0000000000"
    assert headers.get("X-Workspace-Id") == "01JWORKSPACEULID0000000000"
    assert "workspace_id" not in cap["json"], "workspace_id is a header, not a body field"


@pytest.mark.asyncio
async def test_list_sends_workspace_routing_headers():
    client, cap = _capturing_client()
    await client.list_memories(workspace_id="01JWORKSPACEULID0000000000")
    headers = cap["headers"] or {}
    assert headers.get("X-MI-Workspace") == "01JWORKSPACEULID0000000000"
    assert headers.get("X-Workspace-Id") == "01JWORKSPACEULID0000000000"
    assert "workspace_id" not in cap["params"], "workspace_id is a header, not a query param"


@pytest.mark.asyncio
@pytest.mark.parametrize("call", ["ask", "list"])
async def test_untargeted_reads_send_no_routing_headers(call):
    client, cap = _capturing_client()
    if call == "ask":
        await client.ask("q")
    else:
        await client.list_memories()
    assert cap["headers"] is None


@pytest.mark.asyncio
async def test_health_request_shape():
    """The read-isolation probe (#385 UC2) — a plain GET /health, no body."""
    client, cap = _capturing_client()
    await client.health()
    assert cap["method"] == "GET"
    assert cap["path"] == "/health"
    assert cap["json"] is None
    assert cap["params"] == {}


@pytest.mark.asyncio
async def test_capture_scope_id_does_not_route_to_a_workspace():
    """scope_id is governance scope, not workspace routing — it must never
    produce a routing header. (The mi_workspaces tool description used to tell
    agents to pass a workspace ULID as scope_id; that never routed anything.)"""
    client, cap = _capturing_client()
    await client.capture("hello", scope="project", scope_id="01JPROJECTULID00000000000")
    assert cap["headers"] is None
    assert cap["json"]["scope_id"] == "01JPROJECTULID00000000000"
