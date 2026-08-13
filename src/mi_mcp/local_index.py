"""Local vector index + rank over the .umo vault — the heart of local reads.

The vault (`vault.py`) stores owner-encrypted UMOs but has no search. This adds a
local, network-free index so `mi_ask` can rank the vault and return cited results
without touching the API — the structural fix for the cold-start timeout, and the
basis for fully offline reads (no cloud, no model).

DESIGN
------
- Flat numpy cosine. The reality-check measured <1ms for top-k over 50k 384-d
  vectors, so a native HNSW / sqlite-vec dependency is not warranted yet (and it
  would complicate desktop-app notarization). The :class:`LocalIndex` interface is
  the seam to swap in an ANN backend later if a vault ever exceeds ~100k UMOs.
- The rank blends semantic, keyword, entity, and recency signals (weights in
  ``DEFAULT_WEIGHTS``) so local and cloud results stay comparable.

TRUST
-----
The index holds summaries (potentially PII) and embeddings derived from content, so
it MUST live in the local trusted directory alongside the encrypted vault and
inherit the device's at-rest protection (e.g. FileVault).
Encrypting the sidecar with the vault key is a flagged hardening, not yet done.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Sequence

# numpy is a LOCAL-HOSTING dependency (the `local` extra), not part of the thin
# base server-client. Import it lazily inside search() so merely importing this
# module — for its dataclasses or JSON persistence — never requires numpy. Only
# ranking does. Keeps `pip install memoryintelligence-mcp` numpy-free.

# Local ranking weights. The NUMBERS match the cloud's
# (`core/engines/rerank.py`); the SIGNALS underneath are not all identical, so
# read this as "same blend, not the same function" rather than as a parity
# guarantee. Recency is now genuinely shared (see below); keyword and entity
# are still locally derived.
DEFAULT_WEIGHTS = {"semantic": 0.60, "keyword": 0.15, "entity": 0.15, "recency": 0.10}

#: Days over which recency decays to zero. Mirrors `rerank.recency_score`,
#: which the cloud/sidecar read path uses.
RECENCY_HALFLIFE_DAYS = 30.0
_SECONDS_PER_DAY = 86_400.0


def _recency_score(created_at: float, now: float) -> float:
    """Absolute linear 30-day decay — NOT normalized against the corpus (#1253).

    This was ``1.0 - ((now - created_at) / max_age)`` where ``max_age`` was the
    age of the oldest entry in the index. A document's score therefore depended
    on the whole corpus: **importing one old memory reordered every existing
    result**, with no change to the query and no change to the memories being
    ranked. Ranking stopped being a function of ``(query, document)``, which is
    wrong under any architecture we might pick for the local runtime — which is
    why it is fixed here rather than folded into the local/cloud convergence
    question.

    Semantics are reused from ``core/engines/rerank.py::recency_score`` rather
    than re-derived: floor to whole days ago, linear decay over
    ``RECENCY_HALFLIFE_DAYS``, floor at 0.0.

    One deliberate difference from the cloud function, stated rather than
    silent: the result is also capped at **1.0**. A future-dated entry (clock
    skew, a bad import) yields a negative ``days_ago`` there and a score above
    1.0, which would let recency out-rank every real signal. Capping cannot
    hide a real difference — nothing legitimately scores above 1.0.
    """
    days_ago = (now - created_at) // _SECONDS_PER_DAY
    return max(0.0, min(1.0, 1.0 - (days_ago / RECENCY_HALFLIFE_DAYS)))

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
    source: str = ""  # provenance label, carried for citation (not used in ranking)


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

    def get(self, umo_id: str):
        """Return the IndexEntry for a umo_id (or None) — for hydrating hits."""
        return self._entries.get(umo_id)

    def all(self) -> list:
        """All entries, insertion order — for listing surfaces."""
        return list(self._entries.values())

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

        w = self._weights
        hits = []
        for e in self._entries.values():
            v = np.asarray(e.embedding, dtype=float)
            cos = float(np.dot(q, v) / (q_norm * (float(np.linalg.norm(v)) or 1.0)))
            semantic = max(0.0, cos)  # similarity, never negative
            keyword = _overlap(q_tokens, _tokens(e.summary))
            entity = _overlap(q_ents, {x.lower() for x in e.entities}) if q_ents else 0.0
            recency = _recency_score(e.created_at, now)
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
        # Atomic, owner-only: write a 0600 temp then os.replace — a reader never sees a
        # torn/partial sidecar, and there is no 0644 window (the file holds PII summaries).
        tmp = path.with_suffix(path.suffix + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(payload))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, path)

    @classmethod
    def load(cls, path) -> "LocalIndex":
        data = json.loads(Path(path).read_text())
        idx = cls(weights=data.get("weights"))
        # Forward/backward-compatible: ignore unknown keys so a sidecar written by a
        # different IndexEntry version loads (dropping fields) instead of TypeError-ing.
        fields = IndexEntry.__dataclass_fields__
        for raw in data.get("entries", []):
            idx.add(IndexEntry(**{k: v for k, v in raw.items() if k in fields}))
        return idx
