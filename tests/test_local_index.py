"""Tests for the local vault index/rank (Step ① — local reads)."""

import pytest

# numpy backs ranking and ships in the `local` extra, not the thin base. Skip
# (don't error) if a lean env lacks it; CI installs numpy so these run there.
pytest.importorskip("numpy")

from mi_mcp.local_index import IndexEntry, LocalIndex

NOW = 1_000_000.0


def _entry(umo_id, emb, summary="", entities=None, created_at=NOW):
    return IndexEntry(
        umo_id=umo_id,
        embedding=emb,
        summary=summary,
        entities=entities or [],
        created_at=created_at,
    )


def test_empty_index_returns_nothing():
    assert LocalIndex().search(query_embedding=[1, 0, 0]) == []


def test_semantic_ranking_orders_by_similarity():
    idx = LocalIndex()
    idx.add(_entry("a", [1, 0, 0]))
    idx.add(_entry("b", [0, 1, 0]))
    hits = idx.search(query_embedding=[1, 0, 0], now=NOW)
    assert hits[0].umo_id == "a"
    assert hits[0].score > hits[1].score
    assert hits[0].scores["semantic"] == 1.0
    assert hits[1].scores["semantic"] == 0.0


def test_keyword_signal_breaks_a_semantic_tie():
    idx = LocalIndex()
    idx.add(_entry("a", [1, 0, 0], summary="attendance dropped sharply"))
    idx.add(_entry("b", [1, 0, 0], summary="lunch menu options"))
    hits = idx.search(query_embedding=[1, 0, 0], query_text="attendance", now=NOW)
    assert hits[0].umo_id == "a"
    assert hits[0].scores["keyword"] > 0


DAY = 86_400.0


def test_recency_signal_breaks_a_tie():
    """#1253 — rewritten. The old version asserted the BUG.

    It placed two entries 100 seconds apart and asserted recency 1.0 vs 0.0.
    That only held under corpus-relative normalization, where the oldest entry
    defines the scale — so a 100-second gap was stretched into the full range.
    Under an absolute 30-day decay those two entries are the same age (0 days),
    and 1.0 vs 0.0 would be the wrong answer, not the right one.

    The tie now breaks over a real span.
    """
    idx = LocalIndex()
    idx.add(_entry("new", [1, 0, 0], summary="same", created_at=NOW))
    idx.add(_entry("old", [1, 0, 0], summary="same", created_at=NOW - 60 * DAY))
    hits = idx.search(query_embedding=[1, 0, 0], now=NOW)
    assert hits[0].umo_id == "new"
    assert hits[0].scores["recency"] == 1.0
    assert hits[1].scores["recency"] == 0.0


def test_recency_is_absolute_not_corpus_relative():
    """The regression this issue exists for.

    Importing one unrelated OLD memory must not reorder — or even re-score —
    the memories already in the index. Ranking must be a function of
    (query, document), nothing else.
    """
    def _scores(index):
        return {
            h.umo_id: h.scores["recency"]
            for h in index.search(query_embedding=[1, 0, 0], now=NOW)
        }

    idx = LocalIndex()
    idx.add(_entry("a", [1, 0, 0], summary="same", created_at=NOW - 5 * DAY))
    idx.add(_entry("b", [1, 0, 0], summary="same", created_at=NOW - 15 * DAY))
    before = _scores(idx)

    idx.add(_entry("ancient", [0, 1, 0], summary="unrelated",
                   created_at=NOW - 900 * DAY))
    after = _scores(idx)

    assert before["a"] == after["a"], (
        "an unrelated import changed an existing memory's recency score"
    )
    assert before["b"] == after["b"]
    assert [k for k in ("a", "b") if k in after] == ["a", "b"]


def test_recency_matches_the_cloud_reference_implementation():
    """Semantics are REUSED from rerank.recency_score, not re-derived."""
    from mi_mcp.local_index import _recency_score

    for days in (0, 1, 7, 15, 29, 30, 45):
        assert _recency_score(NOW - days * DAY, NOW) == pytest.approx(
            max(0.0, 1.0 - days / 30)
        ), f"diverged from the cloud curve at {days} days"


def test_a_future_dated_entry_cannot_exceed_one():
    """Clock skew must not let recency out-rank every real signal."""
    from mi_mcp.local_index import _recency_score

    assert _recency_score(NOW + 400 * DAY, NOW) == 1.0


def test_entity_signal_applies_when_query_entities_given():
    idx = LocalIndex()
    idx.add(_entry("a", [1, 0, 0], entities=["Maria Gonzalez"]))
    idx.add(_entry("b", [1, 0, 0], entities=["Jamal Brooks"]))
    hits = idx.search(query_embedding=[1, 0, 0], query_entities=["maria gonzalez"], now=NOW)
    assert hits[0].umo_id == "a"
    assert hits[0].scores["entity"] == 1.0
    assert hits[1].scores["entity"] == 0.0


def test_remove_drops_an_entry():
    idx = LocalIndex()
    idx.add(_entry("a", [1, 0, 0]))
    assert "a" in idx
    idx.remove("a")
    assert "a" not in idx
    assert len(idx) == 0


def test_k_limits_results():
    idx = LocalIndex()
    for i in range(5):
        idx.add(_entry(f"u{i}", [1, 0, 0]))
    assert len(idx.search(query_embedding=[1, 0, 0], k=2, now=NOW)) == 2


def test_scores_breakdown_present():
    idx = LocalIndex()
    idx.add(_entry("a", [0.5, 0.5, 0]))
    hit = idx.search(query_embedding=[1, 0, 0], now=NOW)[0]
    assert set(hit.scores) == {"semantic", "keyword", "entity", "recency"}


def test_save_load_round_trip(tmp_path):
    idx = LocalIndex()
    idx.add(_entry("a", [1, 0, 0], summary="alpha", created_at=NOW))
    idx.add(_entry("b", [0, 1, 0], summary="beta", created_at=NOW))
    path = tmp_path / "index.json"
    idx.save(path)

    reloaded = LocalIndex.load(path)
    assert len(reloaded) == 2
    a_before = idx.search(query_embedding=[1, 0, 0], now=NOW)[0]
    a_after = reloaded.search(query_embedding=[1, 0, 0], now=NOW)[0]
    assert a_before.umo_id == a_after.umo_id == "a"
    assert a_before.score == a_after.score
