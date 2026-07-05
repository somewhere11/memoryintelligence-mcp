"""Route reads to the local vault index — the network-free mi_ask / mi_list path.

Phase 1 of local reads (#432). When ``MI_MCP_LOCAL=1`` AND a built index sidecar
exists, ``mi_ask`` / ``mi_list`` answer from the owner's machine: embed the query
locally, rank the prebuilt :class:`~mi_mcp.local_index.LocalIndex`, and emit the
SAME envelope shape the cloud returns — so the output shaper and citation surface
in ``server.py`` work unchanged. Any error degrades to cloud: local is opt-in and
best-effort, cloud stays the default. This is the structural fix for the
``mi_ask`` cold-start timeout (no network round-trip on the read path).

NO KEY AT READ TIME. The index sidecar already carries summary + source +
entities (lifted from the encrypted payload at *build* time, in the CLI, where the
Keychain prompt is acceptable). Serving a read therefore needs only the query
embedder — no ``.umo`` decryption, no owner key. That keeps the read path fast and
Keychain-free, and matches the build-time/read-time split (decision 2026-06-23).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from . import indexer, paths, scrub
from .config import MIConfig
from .local_index import LocalIndex

logger = logging.getLogger("mi_mcp.localreads")

# (mtime, index) — reload the sidecar only when it changes on disk, so a warm
# server doesn't re-read JSON every call but still picks up a rebuild.
_CACHE: Optional[tuple] = None


def available(config: MIConfig) -> bool:
    """True when local reads are enabled and an index has been built."""
    return bool(getattr(config, "local_mode", False)) and paths.local_index_path().exists()


def _get_index() -> Optional[LocalIndex]:
    global _CACHE
    p = paths.local_index_path()
    if not p.exists():
        _CACHE = None
        return None
    mtime = p.stat().st_mtime_ns  # ns granularity — a same-second rebuild still invalidates
    if _CACHE is None or _CACHE[0] != mtime:
        idx = indexer.load_index(p)  # guarded: returns None on a corrupt/incompatible sidecar
        _CACHE = (mtime, idx) if idx is not None else None
    return _CACHE[1] if _CACHE else None


def _iso(epoch: float) -> Optional[str]:
    """Epoch seconds → ISO-8601 (matches the cloud list's created_at shape)."""
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def ask_local(query: str, *, limit: int = 10, offset: int = 0,
              entities: Optional[list] = None) -> dict:
    """Local mi_ask → the cloud ``/v1/memories/query`` envelope shape.

    Raises on any failure (missing index, embedder not installed) so the caller
    falls back to cloud.
    """
    from . import embedder  # lazy: pulls the [local] extra only when actually used

    idx = _get_index()
    if idx is None:
        raise RuntimeError("local index unavailable")
    if offset and offset >= len(idx):
        # paginating past the local total — fall back to cloud rather than returning
        # an empty page that masks results the cloud would have (review H5).
        raise RuntimeError("offset beyond local index size")

    qv = embedder.embed_one(query)
    hits = idx.search(
        query_embedding=qv, query_text=query, query_entities=entities, k=limit + offset
    )
    hits = hits[offset:offset + limit]

    results = []
    for h in hits:
        e = idx.get(h.umo_id)
        ents = e.entities if e else []
        results.append({
            "umo_id": h.umo_id,
            # agent surface → redact before it reaches the LLM (review CR1)
            "summary": scrub.scrub_text(e.summary if e else "", ents),
            "source": (e.source if e else "") or "local",
            "score": h.score,
        })
    return {"data": {"results": results}, "meta": {"backend": "local", "count": len(results)}}


def list_local(*, limit: int = 20, offset: int = 0) -> dict:
    """Local mi_list → the cloud ``GET /v1/memories`` envelope shape (newest first)."""
    idx = _get_index()
    if idx is None:
        raise RuntimeError("local index unavailable")

    entries = sorted(idx.all(), key=lambda e: e.created_at, reverse=True)
    page = entries[offset:offset + limit]
    items = [{
        "umo_id": e.umo_id,
        "summary": scrub.scrub_text(e.summary, e.entities),  # agent surface → redact (CR1)
        "source": e.source or "local",
        # topics reach the LLM via _shape_list — gate them like summary (#433;
        # this was the ungated field in the #506 hold assessment)
        "topics": scrub.scrub_topics(e.topics, e.entities),
        "created_at": _iso(e.created_at),
    } for e in page]
    return {"data": {"items": items}, "meta": {"backend": "local", "count": len(items)}}
