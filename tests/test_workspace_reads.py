"""Workspace READS for mi_ask / mi_list (#385 UC2) — local MCP surface.

UC1 gave the local surface a way to say WHERE a capture goes. UC2 is the read
side: `mi_ask` / `mi_list` take an optional `workspace_id`, symmetric with
`mi_capture` (D3 = option A). Pinned here:

  1. PERSONAL IS THE DEFAULT — omitting workspace_id changes nothing, including
     the output shape (no `scope` wrapper on an untargeted read).
  2. A non-member target is REFUSED, not silently downgraded to personal.
  3. A workspace read must go to the CLOUD — the on-device index has no workspace
     concept, so serving it locally would answer from personal memories under a
     workspace label.
  4. THE OVERCLAIM GUARD: `member_wide_reads` reports whether the server is
     actually returning other members' memories. Server-side read isolation
     (`MI_WORKSPACE_READ_ISOLATION`, #736) is OFF by default, and with it off a
     member-targeted read returns exactly what a personal one returns. An agent
     reading `shared: true, member_count: 4` would otherwise tell the user it
     searched the whole team.

Network-free: fake clients stand in for the API.
"""

from __future__ import annotations

import pytest

from mi_mcp import server as srv
from mi_mcp.config import MIConfig

SHARED_WS = "01JSHAREDWORKSPACE00000000"
SOLO_WS = "01JSOLOWORKSPACE0000000000"

_LISTING = {
    "workspaces": [
        {"workspace_id": SOLO_WS, "name": "Personal", "role": "owner", "member_count": 1},
        {"workspace_id": SHARED_WS, "name": "Somewhere Inc", "role": "admin",
         "member_count": 4},
    ],
    "count": 2,
}


class _FakeClient:
    def __init__(self, *, widening=True, health_raises=False, base_url="https://api.test"):
        self._config = MIConfig(api_key="test-key", base_url=base_url)
        self._widening = widening
        self._health_raises = health_raises
        self.calls: list = []

    async def workspaces(self):
        self.calls.append(("workspaces", None))
        return _LISTING

    async def health(self):
        self.calls.append(("health", None))
        if self._health_raises:
            raise RuntimeError("unreachable")
        caps = {}
        if self._widening is not None:
            caps["workspace_read_isolation"] = {"enabled": self._widening}
        return {"status": "healthy", "capabilities": caps}

    async def ask(self, **kw):
        self.calls.append(("ask", kw))
        return {"status": "success", "data": {"results": []}}

    async def list_memories(self, **kw):
        self.calls.append(("list", kw))
        return {"status": "success", "data": {"items": []}}


@pytest.fixture(autouse=True)
def _clear_widening_cache():
    srv._widening_cache.clear()
    yield
    srv._widening_cache.clear()


# --- 1. personal is the default ---------------------------------------------

@pytest.mark.asyncio
async def test_no_workspace_id_is_personal_and_probes_nothing():
    client = _FakeClient()
    scope, blocked = await srv._resolve_read_scope(client, None)
    assert blocked is None
    assert scope == {"scope": "personal", "shared": False}
    assert client.calls == [], "an untargeted read must not pay any extra round-trip"


def test_personal_read_output_shape_is_unchanged():
    """A personal read returns exactly what it returned before UC2 — no wrapper,
    no scope key. `scope` present == you targeted a workspace."""
    personal = {"scope": "personal", "shared": False}
    assert srv._with_scope({"results": [1]}, personal) == {"results": [1]}
    assert srv._with_scope([1, 2], personal) == [1, 2]


# --- 2. non-member refused, not downgraded ----------------------------------

@pytest.mark.asyncio
async def test_non_member_workspace_read_is_refused():
    client = _FakeClient()
    scope, blocked = await srv._resolve_read_scope(client, "01JNOTMINE0000000000000000")
    assert scope is None
    assert blocked["status"] == "not_a_member"
    # Least disclosure: existence of the workspace is not revealed.
    assert "01JNOTMINE0000000000000000" not in blocked["message"]


# --- 3. a workspace read must not be served from the local index ------------

@pytest.mark.asyncio
async def test_workspace_ask_bypasses_the_local_index(monkeypatch):
    """The on-device index holds personal memories and knows nothing about
    workspaces — answering a workspace query from it would be a labelled lie."""
    monkeypatch.setattr(srv.localreads, "available", lambda cfg: True)
    monkeypatch.setattr(srv.localreads, "ask_local", lambda *a, **k: pytest.fail(
        "workspace-targeted mi_ask was served from the local index"
    ))
    client = _FakeClient()
    await srv._route_ask(client._config, client, {"query": "q", "workspace_id": SHARED_WS})
    assert client.calls[-1][0] == "ask"
    assert client.calls[-1][1]["workspace_id"] == SHARED_WS


@pytest.mark.asyncio
async def test_workspace_list_bypasses_the_local_index(monkeypatch):
    monkeypatch.setattr(srv.localreads, "available", lambda cfg: True)
    monkeypatch.setattr(srv.localreads, "list_local", lambda *a, **k: pytest.fail(
        "workspace-targeted mi_list was served from the local index"
    ))
    client = _FakeClient()
    await srv._route_list(client._config, client, {"workspace_id": SHARED_WS})
    assert client.calls[-1][0] == "list"
    assert client.calls[-1][1]["workspace_id"] == SHARED_WS


@pytest.mark.asyncio
async def test_personal_ask_still_uses_the_local_index(monkeypatch):
    """UC2 must not disable local reads for everyone who didn't ask for a workspace."""
    monkeypatch.setattr(srv.localreads, "available", lambda cfg: True)
    monkeypatch.setattr(srv.localreads, "ask_local",
                        lambda *a, **k: {"served": "local"})
    client = _FakeClient()
    out = await srv._route_ask(client._config, client, {"query": "q"})
    assert out == {"served": "local"}
    assert client.calls == []


# --- 4. the overclaim guard --------------------------------------------------

@pytest.mark.asyncio
async def test_widening_on_reports_member_wide_reads_and_no_warning():
    client = _FakeClient(widening=True)
    scope, _ = await srv._resolve_read_scope(client, SHARED_WS)
    assert scope["member_wide_reads"] is True
    assert scope["shared"] is True
    assert scope["member_count"] == 4
    assert "note" not in scope


@pytest.mark.asyncio
async def test_widening_off_on_a_shared_workspace_carries_the_warning():
    """The failure this exists to prevent: reporting a 4-member team scope on a
    read that returned only the caller's own memories."""
    client = _FakeClient(widening=False)
    scope, _ = await srv._resolve_read_scope(client, SHARED_WS)
    assert scope["member_wide_reads"] is False
    assert "note" in scope
    assert "NOT returning their memories" in scope["note"]
    assert "Do not tell the user you searched the whole team workspace" in scope["note"]


@pytest.mark.asyncio
async def test_widening_off_on_a_solo_workspace_has_no_warning():
    """Nothing is being withheld from a 1-member workspace — no scary note."""
    client = _FakeClient(widening=False)
    scope, _ = await srv._resolve_read_scope(client, SOLO_WS)
    assert scope["member_wide_reads"] is False
    assert scope["shared"] is False
    assert "note" not in scope


@pytest.mark.asyncio
async def test_unreachable_health_reports_unknown_not_a_guess():
    client = _FakeClient(health_raises=True)
    scope, _ = await srv._resolve_read_scope(client, SHARED_WS)
    assert scope["member_wide_reads"] == srv._WIDENING_UNKNOWN
    assert "unknown state" in scope["note"]


@pytest.mark.asyncio
async def test_older_server_without_the_capability_reports_unknown_and_is_not_cached():
    """A server predating the capability must not be read as 'disabled', and the
    unknown must not stick — a later deploy should start answering."""
    client = _FakeClient(widening=None)
    assert await srv._member_wide_reads_enabled(client) == srv._WIDENING_UNKNOWN
    assert srv._widening_cache == {}


@pytest.mark.asyncio
async def test_widening_probe_is_cached_per_process():
    """The flag is an env var — it cannot change without a redeploy, so a read
    must not pay a /health round-trip every call."""
    client = _FakeClient(widening=True)
    for _ in range(3):
        await srv._resolve_read_scope(client, SHARED_WS)
    assert [c[0] for c in client.calls].count("health") == 1


# --- the scope block reaches the agent --------------------------------------

def test_scope_is_attached_to_both_result_shapes():
    scope = {"scope": "workspace", "workspace_id": SHARED_WS, "name": "Somewhere Inc"}
    # _shape_ask yields a dict
    assert srv._with_scope({"results": [1]}, scope) == {"results": [1], "scope": scope}
    # _shape_list yields a bare list
    assert srv._with_scope([1, 2], scope) == {"scope": scope, "items": [1, 2]}


def test_read_tools_advertise_workspace_id():
    import asyncio

    from mcp.types import ListToolsRequest

    from mi_mcp.server import create_server

    server = create_server(MIConfig(api_key="test-key"))
    result = asyncio.run(server.request_handlers[ListToolsRequest](None))
    tools = {t.name: t for t in result.root.tools}
    for name in ("mi_ask", "mi_list"):
        assert "workspace_id" in tools[name].inputSchema["properties"], name
        # The agent must be told to check member_wide_reads before claiming a
        # team-wide search — the parameter alone invites the overclaim.
        assert "member_wide_reads" in tools[name].inputSchema["properties"]["workspace_id"]["description"]
