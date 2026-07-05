"""Tests for the local read path (Phase 1) — mi_ask / mi_list served from the vault index.

No embedding model and no network: ``embedder.embed_one`` is monkeypatched to a
fixed query vector, and the index is built in-memory with known vectors. The key
contract under test is that ``ask_local`` / ``list_local`` emit the SAME envelope
the cloud does, so ``server._shape_ask`` / ``_shape_list`` project them unchanged.
"""

from __future__ import annotations

import pytest

pytest.importorskip("numpy")

from mi_mcp import indexer, localreads, paths, scrub  # noqa: E402
from mi_mcp.config import MIConfig  # noqa: E402
from mi_mcp.local_index import IndexEntry, LocalIndex  # noqa: E402
from mi_mcp.server import _route_ask, _route_list, _shape_ask, _shape_list  # noqa: E402


class _FakeClient:
    """Records calls + returns a cloud-shaped sentinel, so routing tests can tell
    whether the local path or the cloud client answered."""

    def __init__(self):
        self.ask_calls = []
        self.list_calls = []

    async def ask(self, **kw):
        self.ask_calls.append(kw)
        return {"data": {"results": [{"umo_id": "cloud", "summary": "c", "source": "c", "score": 0}]}}

    async def list_memories(self, **kw):
        self.list_calls.append(kw)
        return {"data": {"items": [{"umo_id": "cloud"}]}}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("MI_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(localreads, "_CACHE", None)  # reset the mtime cache
    # Pin the scrubber to its in-package floor so envelope assertions are
    # deterministic in both environments (the repo venv can import the core
    # detector; the mcp-server CI job cannot). The strong path has its own
    # tests in test_scrub.py.
    monkeypatch.setattr(scrub, "_scrub_with_core", lambda t: None)
    yield


def _cfg(local_mode):
    return MIConfig(api_key="x", local_mode=local_mode)


def _build_sidecar():
    idx = LocalIndex()
    idx.add(IndexEntry(umo_id="u-a", embedding=[1, 0, 0], summary="postgres for billing",
                       source="conversation", topics=["db"], created_at=200.0))
    idx.add(IndexEntry(umo_id="u-b", embedding=[0, 1, 0], summary="lunch menu",
                       source="notes", topics=["food"], created_at=100.0))
    indexer.save_index(idx)


# --- availability gate ------------------------------------------------------

def test_available_requires_flag_and_index():
    assert localreads.available(_cfg(local_mode=False)) is False  # flag off
    assert localreads.available(_cfg(local_mode=True)) is False   # no index yet
    _build_sidecar()
    assert localreads.available(_cfg(local_mode=True)) is True
    assert localreads.available(_cfg(local_mode=False)) is False  # flag still gates


# --- ask_local --------------------------------------------------------------

def test_ask_local_envelope_feeds_shape_ask(monkeypatch):
    _build_sidecar()
    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda q: [1, 0, 0])

    env = localreads.ask_local("billing database?", limit=10)
    assert env["meta"]["backend"] == "local"
    assert env["data"]["results"][0]["umo_id"] == "u-a"

    shaped = _shape_ask(env)  # the server applies this before returning
    assert isinstance(shaped, list)
    assert shaped[0] == {
        "umo_id": "u-a", "summary": "postgres for billing",
        "source": "conversation", "score": pytest.approx(shaped[0]["score"]),
    }
    assert set(shaped[0]) == {"umo_id", "summary", "source", "score"}


def test_ask_local_respects_limit(monkeypatch):
    _build_sidecar()
    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda q: [1, 0, 0])
    env = localreads.ask_local("x", limit=1)
    assert len(env["data"]["results"]) == 1


def test_ask_local_raises_without_index(monkeypatch):
    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda q: [1, 0, 0])
    with pytest.raises(Exception):  # caller catches → cloud fallback
        localreads.ask_local("x")


# --- list_local -------------------------------------------------------------

def test_list_local_envelope_feeds_shape_list():
    _build_sidecar()
    env = localreads.list_local(limit=20)
    assert env["meta"]["backend"] == "local"

    shaped = _shape_list(env)
    assert [it["umo_id"] for it in shaped] == ["u-a", "u-b"]  # newest (created_at) first
    assert set(shaped[0]) == {"umo_id", "summary", "source", "topics", "created_at"}
    assert shaped[0]["created_at"].startswith("1970")  # epoch 200 → ISO


def test_list_local_paginates():
    _build_sidecar()
    env = localreads.list_local(limit=1, offset=1)
    assert [it["umo_id"] for it in env["data"]["items"]] == ["u-b"]


# --- cache invalidation -----------------------------------------------------

def test_index_cache_reloads_on_rebuild(monkeypatch):
    _build_sidecar()
    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda q: [1, 0, 0])
    assert len(localreads.ask_local("x", limit=10)["data"]["results"]) == 2

    # rebuild with a different sidecar, then force a distinct mtime so the cache
    # invalidation is deterministic regardless of filesystem timestamp resolution.
    idx = LocalIndex()
    idx.add(IndexEntry(umo_id="only", embedding=[1, 0, 0], summary="s"))
    indexer.save_index(idx)
    p = paths.local_index_path()
    import os
    os.utime(p, (1_000_000_000, 1_000_000_000))  # fixed, distinct from the cached mtime
    assert [r["umo_id"] for r in localreads.ask_local("x")["data"]["results"]] == ["only"]


# --- egress scrub on the local serve path (review CR1) ----------------------

def test_ask_local_scrubs_pii_before_returning(monkeypatch):
    idx = LocalIndex()
    idx.add(IndexEntry(umo_id="p", embedding=[1, 0, 0],
                       summary="email bob@x.io, Maria Gonzalez called", entities=["Maria Gonzalez"]))
    indexer.save_index(idx)
    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda q: [1, 0, 0])
    s = localreads.ask_local("x")["data"]["results"][0]["summary"]
    assert "bob@x.io" not in s and "<EMAIL>" in s
    assert "Maria Gonzalez" not in s and "<ENTITY>" in s


def test_list_local_scrubs_topics():
    # topics reach the LLM via _shape_list — the ungated field from the #506
    # hold assessment. A name-as-topic and an email-as-topic must both scrub.
    idx = LocalIndex()
    idx.add(IndexEntry(umo_id="t", embedding=[1, 0, 0], summary="ok",
                       entities=["Maria Gonzalez"],
                       topics=["Maria Gonzalez", "budget", "a.b@x.io"]))
    indexer.save_index(idx)
    items = localreads.list_local()["data"]["items"]
    assert items[0]["topics"] == ["<ENTITY>", "budget", "<EMAIL>"]


def test_reembed_fallback_summary_scrubbed_at_egress():
    # Hold-assessment gap 4: indexer._reembed_entry can fall back to raw
    # content[:200] as the summary. Whatever landed in the sidecar, the egress
    # scrub still gates it.
    idx = LocalIndex()
    idx.add(IndexEntry(umo_id="r", embedding=[1, 0, 0],
                       summary="raw head: ssn 123-45-6789, reach bob@x.io"))
    indexer.save_index(idx)
    s = localreads.list_local()["data"]["items"][0]["summary"]
    assert "123-45-6789" not in s and "bob@x.io" not in s


def test_agent_surface_scrub_is_not_overridable():
    # #433 acceptance criterion: redaction is non-overridable on the agent
    # surface — the local read API exposes NO raw/redact switch. Raw stays on
    # the human surfaces (desktop app, `mi-mcp memory open`).
    import inspect
    for fn in (localreads.ask_local, localreads.list_local):
        params = inspect.signature(fn).parameters
        assert "redact" not in params and "raw" not in params


def test_ask_local_offset_beyond_total_raises_for_fallback(monkeypatch):
    _build_sidecar()  # 2 entries
    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda q: [1, 0, 0])
    with pytest.raises(Exception):
        localreads.ask_local("x", offset=50)


# --- server routing + cloud fallback (review CR4) ---------------------------

async def test_route_ask_prefers_local_and_does_not_call_cloud(monkeypatch):
    _build_sidecar()
    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda q: [1, 0, 0])
    c = _FakeClient()
    r = await _route_ask(_cfg(True), c, {"query": "x"})
    assert r["meta"]["backend"] == "local"
    assert c.ask_calls == []


async def test_route_ask_falls_back_to_cloud_on_local_error(monkeypatch):
    _build_sidecar()
    def boom(*a, **k):
        raise RuntimeError("local boom")
    monkeypatch.setattr("mi_mcp.localreads.ask_local", boom)
    c = _FakeClient()
    r = await _route_ask(_cfg(True), c, {"query": "x"})
    assert r["data"]["results"][0]["umo_id"] == "cloud"
    assert len(c.ask_calls) == 1


async def test_route_ask_advanced_filter_goes_to_cloud(monkeypatch):
    _build_sidecar()
    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda q: [1, 0, 0])
    c = _FakeClient()
    await _route_ask(_cfg(True), c, {"query": "x", "date_from": "2026-01-01"})
    assert len(c.ask_calls) == 1  # advanced filter → cloud despite local available


async def test_route_ask_cloud_when_local_disabled():
    c = _FakeClient()
    await _route_ask(_cfg(False), c, {"query": "x"})
    assert len(c.ask_calls) == 1


async def test_route_list_local_then_cloud(monkeypatch):
    _build_sidecar()
    c = _FakeClient()
    r = await _route_list(_cfg(True), c, {})
    assert r["meta"]["backend"] == "local" and c.list_calls == []
    await _route_list(_cfg(False), c, {})
    assert len(c.list_calls) == 1


# --- config parsing ---------------------------------------------------------

def test_local_mode_parsed_from_env(monkeypatch):
    monkeypatch.setenv("MI_API_KEY", "k")
    monkeypatch.setenv("MI_MCP_LOCAL", "1")
    assert MIConfig.from_env().local_mode is True
    monkeypatch.delenv("MI_MCP_LOCAL")
    assert MIConfig.from_env().local_mode is False
