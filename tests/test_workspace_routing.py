"""Workspace routing for mi_capture (#385 UC1 + UC1.5) — local MCP surface.

The backend has routed captures by workspace since #736/#385; the local MCP
package could not *express* a target until 0.2.7 — `mi_capture` had no
`workspace_id` and `MIClient.capture()` sent no routing header. These tests pin
the behaviour that closes that gap, and the safety contract that comes with it:

  1. PERSONAL IS THE DEFAULT — no workspace_id → no routing, no extra API call.
  2. A SHARED workspace (>1 member) write needs an explicit confirm and saves
     NOTHING without it. This is the rule that stops a single silent call from
     posting a memory into a team space.
  3. Every routed capture NAMES its destination, so "where did that go" is always
     answerable from the response.
  4. A non-member target is refused, never silently downgraded to personal —
     a reported destination must never be a lie.

Network-free: a fake client stands in for the API.
"""

from __future__ import annotations

import pytest

from mi_mcp.server import (
    _confirmed,
    _resolve_capture_destination,
    _shared_write_confirm_required,
)

SHARED_WS = "01JSHAREDWORKSPACE00000000"
SOLO_WS = "01JSOLOWORKSPACE0000000000"

_LISTING = {
    "workspaces": [
        {"workspace_id": SOLO_WS, "name": "Personal", "slug": "personal",
         "role": "owner", "member_count": 1},
        {"workspace_id": SHARED_WS, "name": "Somewhere Inc", "slug": "somewhere",
         "role": "admin", "member_count": 4},
    ],
    "count": 2,
}


class _FakeClient:
    """Stands in for MIClient — records whether /v1/workspaces was called."""

    def __init__(self, listing=None):
        self._listing = _LISTING if listing is None else listing
        self.workspaces_calls = 0

    async def workspaces(self):
        self.workspaces_calls += 1
        return self._listing


# --- 1. personal is the default ---------------------------------------------

@pytest.mark.asyncio
async def test_no_workspace_id_is_personal_and_costs_no_lookup():
    client = _FakeClient()
    destination, blocked = await _resolve_capture_destination(client, None)
    assert blocked is None
    assert destination == {"scope": "personal", "shared": False}
    assert client.workspaces_calls == 0, (
        "an untargeted capture must not pay a /v1/workspaces round-trip"
    )


# --- 2. the shared-write confirm gate ---------------------------------------

@pytest.mark.asyncio
async def test_shared_workspace_without_confirm_is_blocked():
    client = _FakeClient()
    destination, blocked = await _resolve_capture_destination(client, SHARED_WS)
    assert blocked is None  # membership is fine; the gate is the next step
    gate = _shared_write_confirm_required(destination, confirm=False)
    assert gate is not None, "a shared-workspace write must not proceed unconfirmed"
    assert gate["status"] == "confirm_required"
    assert gate["destination"]["name"] == "Somewhere Inc"
    assert gate["destination"]["member_count"] == 4
    # The message must tell the agent that nothing was written — an agent that
    # believes the memory saved will not re-call after the user confirms.
    assert "Nothing has been saved" in gate["message"]


@pytest.mark.asyncio
async def test_shared_workspace_with_confirm_proceeds():
    client = _FakeClient()
    destination, _ = await _resolve_capture_destination(client, SHARED_WS)
    assert _shared_write_confirm_required(destination, confirm=True) is None


@pytest.mark.parametrize("confirm", ["false", "no", "0", 0, 1, "true", "True", [], {}, None])
def test_only_the_literal_boolean_true_counts_as_confirmation(confirm):
    """The schema says boolean, but the caller is a language model: `confirm` can
    arrive as the STRING "false", and `bool("false")` is True — which would post into
    a team space on an unconfirmed call. Every confirm gate on this surface fails
    closed on anything that is not literally `true`.

    Note `"true"` and `1` are refused too: this is deliberately strict. A gate that
    guesses at intent is not a gate.
    """
    assert _confirmed({"confirm": confirm}) is False


def test_missing_confirm_is_not_confirmation():
    assert _confirmed({}) is False


def test_boolean_true_is_confirmation():
    """Fail-closed, not fail-shut — a genuine confirm must still get through."""
    assert _confirmed({"confirm": True}) is True
    destination = {"shared": True, "name": "Somewhere Inc", "member_count": 4}
    assert _shared_write_confirm_required(destination, _confirmed({"confirm": True})) is None


@pytest.mark.parametrize("confirm", ["false", "0", None])
def test_shared_write_stays_gated_for_every_non_boolean_confirm(confirm):
    """The end-to-end consequence: a non-True confirm leaves the hard gate closed."""
    destination = {"shared": True, "name": "Somewhere Inc", "member_count": 4}
    gate = _shared_write_confirm_required(destination, _confirmed({"confirm": confirm}))
    assert gate is not None and gate["status"] == "confirm_required"


@pytest.mark.asyncio
async def test_solo_workspace_needs_no_confirm():
    """A 1-member workspace is not 'sharing' — confirm friction there is noise."""
    client = _FakeClient()
    destination, blocked = await _resolve_capture_destination(client, SOLO_WS)
    assert blocked is None
    assert destination["shared"] is False
    assert _shared_write_confirm_required(destination, confirm=False) is None


@pytest.mark.asyncio
async def test_personal_needs_no_confirm():
    client = _FakeClient()
    destination, _ = await _resolve_capture_destination(client, None)
    assert _shared_write_confirm_required(destination, confirm=False) is None


# --- 3. destination feedback -------------------------------------------------

@pytest.mark.asyncio
async def test_destination_names_the_workspace():
    client = _FakeClient()
    destination, _ = await _resolve_capture_destination(client, SHARED_WS)
    assert destination == {
        "scope": "workspace",
        "workspace_id": SHARED_WS,
        "name": "Somewhere Inc",
        "role": "admin",
        "shared": True,
        "member_count": 4,
    }


@pytest.mark.asyncio
async def test_missing_member_count_defaults_to_not_shared():
    """A listing without member_count must not crash — and must not invent
    sharing. It falls back to 1 (solo), matching the remote surface."""
    client = _FakeClient({"workspaces": [{"workspace_id": SOLO_WS, "name": "W"}]})
    destination, blocked = await _resolve_capture_destination(client, SOLO_WS)
    assert blocked is None
    assert destination["member_count"] == 1
    assert destination["shared"] is False


# --- 4. a non-member target is refused, not downgraded ----------------------

@pytest.mark.asyncio
async def test_non_member_workspace_is_refused():
    client = _FakeClient()
    destination, blocked = await _resolve_capture_destination(client, "01JNOTMINE0000000000000000")
    assert destination is None
    assert blocked is not None, (
        "a non-member target must be refused — silently capturing it to personal "
        "would report a destination the memory never went to"
    )
    assert blocked["status"] == "not_a_member"
    # Least disclosure: don't tell the caller whether the workspace exists.
    assert "01JNOTMINE0000000000000000" not in blocked["message"]


@pytest.mark.asyncio
async def test_empty_listing_refuses_every_target():
    client = _FakeClient({"workspaces": [], "count": 0})
    destination, blocked = await _resolve_capture_destination(client, SHARED_WS)
    assert destination is None
    assert blocked["status"] == "not_a_member"


@pytest.mark.asyncio
async def test_lookup_failure_propagates_rather_than_capturing_blind():
    """If /v1/workspaces fails we must NOT fall through to an unrouted capture —
    the agent would be told nothing and the memory would land in home."""
    class _Broken(_FakeClient):
        async def workspaces(self):
            raise RuntimeError("api down")

    with pytest.raises(RuntimeError):
        await _resolve_capture_destination(_Broken(), SHARED_WS)


# --- the tool schema actually advertises the parameters ---------------------

def test_mi_capture_schema_advertises_workspace_id_and_confirm():
    """The wiring is only real if the agent can SEE the parameter. Pins the
    schema so a refactor can't drop it back to the documented-but-absent state."""
    import asyncio

    from mi_mcp.config import MIConfig
    from mi_mcp.server import create_server

    server = create_server(MIConfig(api_key="test-key"))
    handler = server.request_handlers[__import__("mcp.types", fromlist=["ListToolsRequest"]).ListToolsRequest]
    result = asyncio.run(handler(None))
    tools = {t.name: t for t in result.root.tools}

    props = tools["mi_capture"].inputSchema["properties"]
    assert "workspace_id" in props
    assert "confirm" in props
    assert props["confirm"]["type"] == "boolean"
    # confirm must stay OPTIONAL — requiring it would force every personal
    # capture through a gate that exists only for shared workspaces.
    assert tools["mi_capture"].inputSchema["required"] == ["content"]
    # The routing tool must point agents at workspace_id, not scope_id.
    assert "workspace_id" in tools["mi_workspaces"].description
    assert "scope_id" not in tools["mi_workspaces"].description
