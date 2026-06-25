"""Local vector index + rank over the .umo vault — the heart of local reads.

The vault (`vault.py`) stores owner-encrypted UMOs but has no search. This adds a
local, network-free index so `mi_ask` can rank the vault and return cited results
without touching the API — the structural fix for the cold-start timeout, and the
foundation of the FERPA "MI Local" school tier (no cloud, no model).

DESIGN
------
- Flat numpy cosine. The reality-check measured <1ms for top-k over 50k 384-d
  vectors, so a native HNSW / sqlite-vec dependency is not warranted yet (and it
  would complicate desktop-app notarization). The :class:`LocalIndex` interface is
  the seam to swap in an ANN backend later if a vault ever exceeds ~100k UMOs.
- The rank mirrors the server formula (`api/public/search.py`):
  ``semantic*0.60 + keyword*0.15 + entity*0.15 + recency*0.10`` — so local and
  cloud ranking stay comparable.

TRUST
-----
The index holds summaries (potentially PII) and embeddings derived from content, so
it MUST live in the local trusted directory alongside the encrypted vault and
inherit the device's at-rest protection (e.g. FileVault, per the school-tier spec).
Encrypting the sidecar with the vault key is a flagged hardening, not yet done.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Sequence

# numpy is a LOCAL-HOSTING dependency (the `local` extra), not part of the thin
# base server-client. Import it lazily inside search() so merely importing this
# module — for its dataclasses or JSON persistence — never requires numpy. Only
# ranking does. Keeps `pip install memoryintelligence-mcp` numpy-free.

# Mirrors api/public/search.py so local and cloud ranking are comparable.
DEFAULT_WEIGHTS = {"semantic": 0.60, "keyword": 0.15, "entity": 0.15, "recency": 0.10}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall(text.lower())) if text else set()


def _overlap(a: set, b: set) -> float:
    """Jaccard overlap in [0, 1]."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class IndexEntry:
    umo_id: str
    embedding: list  # 384-d (bge-small) — same model as capture, or vectors won't match
    summary: str = ""
    entities: list = field(default_factory=list)
    topics: list = field(default_factory=list)
    created_at: float = 0.0  # epoch seconds


@dataclass
class ScoredHit:
    umo_id: str
    score: float
    scores: dict  # per-signal breakdown, for explain/audit parity with the API


class LocalIndex:
    """In-memory flat-vector index with a JSON sidecar, over the local vault."""

    def __init__(self, weights: Optional[dict] = None):
        self._entries: dict = {}
        self._weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    def add(self, entry: IndexEntry) -> None:
        self._entries[entry.umo_id] = entry

    def remove(self, umo_id: str) -> None:
        self._entries.pop(umo_id, None)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, umo_id: str) -> bool:
        return umo_id in self._entries

    def search(
        self,
        *,
        query_embedding: Sequence[float],
        query_text: str = "",
        query_entities: Optional[Sequence[str]] = None,
        k: int = 10,
        now: Optional[float] = None,
    ) -> list:
        """Return the top-k ScoredHits, highest score first.

        ``now`` is injectable so ranking is deterministic in tests; defaults to wall
        clock for the recency signal.
        """
        if not self._entries:
            return []
        import numpy as np  # lazy: only ranking needs numpy (see module note)

        now = now if now is not None else time.time()

        q = np.asarray(query_embedding, dtype=float)
        q_norm = float(np.linalg.norm(q)) or 1.0
        q_tokens = _tokens(query_text)
        q_ents = {e.lower() for e in (query_entities or [])}

        ages = [now - e.created_at for e in self._entries.values()]
        max_age = max(ages) or 1.0  # normalize recency against the oldest entry

        w = self._weights
        hits = []
        for e in self._entries.values():
            v = np.asarray(e.embedding, dtype=float)
            cos = float(np.dot(q, v) / (q_norm * (float(np.linalg.norm(v)) or 1.0)))
            semantic = max(0.0, cos)  # similarity, never negative
            keyword = _overlap(q_tokens, _tokens(e.summary))
            entity = _overlap(q_ents, {x.lower() for x in e.entities}) if q_ents else 0.0
            recency = 1.0 - ((now - e.created_at) / max_age)
            score = (
                w["semantic"] * semantic
                + w["keyword"] * keyword
                + w["entity"] * entity
                + w["recency"] * recency
            )
            hits.append(
                ScoredHit(
                    e.umo_id,
                    round(score, 6),
                    {
                        "semantic": round(semantic, 4),
                        "keyword": round(keyword, 4),
                        "entity": round(entity, 4),
                        "recency": round(recency, 4),
                    },
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    # ----- persistence (LOCAL trusted dir only) -----

    def save(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "weights": self._weights,
            "entries": [asdict(e) for e in self._entries.values()],
        }
        path.write_text(json.dumps(payload))

    @classmethod
    def load(cls, path) -> "LocalIndex":
        data = json.loads(Path(path).read_text())
        idx = cls(weights=data.get("weights"))
        for raw in data.get("entries", []):
            idx.add(IndexEntry(**raw))
        return idx
