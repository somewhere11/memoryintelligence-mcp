"""Tests for the index builder (0c) — vault → decrypt → LocalIndex → sidecar.

No network and no embedding model: ``.umo`` files are produced with KNOWN
embedding vectors in the payload, exactly as backfill writes them, so the builder,
ranking, and sidecar round-trip are all exercised offline.
"""

from __future__ import annotations

import base64

import pytest

cryptography = pytest.importorskip("cryptography")
pytest.importorskip("numpy")

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519  # noqa: E402

from mi_mcp import indexer, keys, paths, umo_format, vault  # noqa: E402
from mi_mcp.cli import _payload_for_umo, _public_metadata_for_umo  # noqa: E402


def _raw_priv_b64(priv: x25519.X25519PrivateKey) -> str:
    return base64.b64encode(
        priv.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
    ).decode()


@pytest.fixture
def owner_env(tmp_path, monkeypatch):
    """Owner master key (env) + tmp vault + tmp hidden home (for the sidecar)."""
    priv = x25519.X25519PrivateKey.generate()
    monkeypatch.setenv("MI_MASTER_KEY", _raw_priv_b64(priv))
    monkeypatch.setenv("MI_VAULT", str(tmp_path / "vault"))
    monkeypatch.setenv("MI_HOME", str(tmp_path / "home"))
    # owner's Ed25519 signing key — files signed with it pass build-time verification
    sraw = ed25519.Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption(),
    )
    monkeypatch.setenv("MI_LOCAL_SIGNING_KEY", base64.b64encode(sraw).decode())
    return priv


def _write_umo(owner_pub, signing, *, umo_id, embedding, summary="", entities=None,
               tags=None, created_at="2026-06-20T00:00:00Z", owner_did="did:mi:test"):
    """Produce + write a .umo exactly as backfill does (via the cli payload helpers)."""
    row = {
        "id": umo_id, "summary": summary, "entities": entities or [],
        "tags": tags or [], "created_at": created_at, "normalized_text": summary,
    }
    payload = _payload_for_umo(row, embedding)
    pm = _public_metadata_for_umo(row, owner_did)
    blob = umo_format.produce_umo_for_owner(payload, pm, owner_pub, signing)
    return vault.write_umo(umo_id, owner_did, blob)


# --- pure helpers ----------------------------------------------------------

def test_entity_names_handles_strings_and_dicts():
    assert indexer._entity_names(["Maria", {"text": "Jamal"}, {"name": "Ada"}]) == [
        "Maria", "Jamal", "Ada",
    ]
    assert indexer._entity_names(None) == []
    assert indexer._entity_names([{"type": "PERSON"}]) == []  # no name key → dropped


def test_to_epoch_parses_iso_and_passes_numbers():
    assert indexer._to_epoch(1000.0) == 1000.0
    assert indexer._to_epoch("2026-06-20T00:00:00Z") > 0
    assert indexer._to_epoch("") == 0.0
    assert indexer._to_epoch("not-a-date") == 0.0


def test_to_epoch_naive_iso_treated_as_utc():
    # a timezone-naive timestamp must equal its UTC-aware twin, not be shifted to local
    assert indexer._to_epoch("2026-06-01T12:00:00") == indexer._to_epoch("2026-06-01T12:00:00+00:00")


def test_entry_from_payload_requires_embedding():
    assert indexer.entry_from_payload({"summary": "x"}, {"umo_id": "a"}) is None
    e = indexer.entry_from_payload(
        {"embedding": [1, 0, 0], "summary": "hi", "entities": [{"text": "Bob"}]},
        {"umo_id": "a", "created_at": "2026-06-20T00:00:00Z"},
    )
    assert e is not None and e.umo_id == "a" and e.entities == ["Bob"]


# --- build from the vault --------------------------------------------------

def test_build_index_from_vault_decrypts_and_ranks(owner_env):
    owner_priv = keys.load_master_private_key()
    owner_pub = owner_priv.public_key()
    signing = keys.load_local_signing_key()  # owner signing key (env) → passes verify

    _write_umo(owner_pub, signing, umo_id="u-a", embedding=[1, 0, 0],
               summary="attendance dropped", entities=[{"text": "Maria"}])
    _write_umo(owner_pub, signing, umo_id="u-b", embedding=[0, 1, 0],
               summary="lunch menu")

    idx = indexer.build_index_from_vault(owner_priv=owner_priv)
    assert len(idx) == 2

    hits = idx.search(query_embedding=[1, 0, 0], query_text="attendance")
    assert hits[0].umo_id == "u-a"
    assert hits[0].score > hits[1].score


def test_foreign_umo_is_skipped_not_fatal(owner_env):
    owner_priv = keys.load_master_private_key()
    signing = keys.load_local_signing_key()  # owner signing key (env) → passes verify

    # one of ours …
    _write_umo(owner_priv.public_key(), signing, umo_id="ours", embedding=[1, 0, 0])
    # … and one encrypted for a DIFFERENT owner (can't decrypt → skipped)
    other = x25519.X25519PrivateKey.generate().public_key()
    _write_umo(other, signing, umo_id="theirs", embedding=[0, 1, 0])

    idx = indexer.build_index_from_vault(owner_priv=owner_priv)
    assert "ours" in idx and "theirs" not in idx
    assert len(idx) == 1


def test_rebuild_and_save_then_load_round_trips(owner_env):
    owner_priv = keys.load_master_private_key()
    signing = keys.load_local_signing_key()  # owner signing key (env) → passes verify
    _write_umo(owner_priv.public_key(), signing, umo_id="x", embedding=[1, 0, 0],
               summary="alpha")

    count = indexer.rebuild_and_save(owner_priv=owner_priv)
    assert count == 1
    sidecar = paths.local_index_path()
    assert sidecar.exists()
    # PII-bearing sidecar is owner-only at rest (matches the keyfile chmod stance)
    assert (sidecar.stat().st_mode & 0o777) == 0o600

    reloaded = indexer.load_index()
    assert reloaded is not None and len(reloaded) == 1
    assert reloaded.search(query_embedding=[1, 0, 0])[0].umo_id == "x"


def test_load_index_absent_returns_none(owner_env):
    assert indexer.load_index() is None


def test_build_reembeds_flat_text_only_payload(owner_env, monkeypatch):
    # A flat .umo whose payload has TEXT but NO embedding must be re-embedded so it
    # enters the index (covers MCP-style text-only writes).
    owner_priv = keys.load_master_private_key()
    signing = keys.load_local_signing_key()  # owner signing key (env) → passes verify
    payload = {"normalized_text": "the quarterly board meeting moved to Friday"}
    pm = {"umo_id": "no-vec", "created_at": "2026-06-20T00:00:00Z"}
    blob = umo_format.produce_umo_for_owner(payload, pm, owner_priv.public_key(), signing)
    vault.write_umo("no-vec", "did:mi:owner-local", blob)

    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda t: [0.0, 1.0, 0.0])
    idx = indexer.build_index_from_vault(owner_priv=owner_priv)
    assert "no-vec" in idx
    e = idx.get("no-vec")
    assert e.embedding == [0.0, 1.0, 0.0]
    assert "board meeting" in e.summary  # summary fell back to the text snippet


def test_build_reembeds_REAL_nested_desktop_payload(owner_env, monkeypatch):
    # The desktop writes a NESTED payload: {semantic:{claim,entities}, temporal, provenance}.
    # The indexer must read it (claim→summary, semantic.entities, provenance.source,
    # temporal.observed_at) and re-embed — this is the unification the straw test missed.
    owner_priv = keys.load_master_private_key()
    signing = keys.load_local_signing_key()  # owner signing key (env) → passes verify
    payload = {
        "semantic": {"claim": "we picked Postgres for billing", "entities": [{"text": "Postgres"}]},
        "temporal": {"observed_at": "2026-06-21T00:00:00Z"},
        "provenance": {"source": "somewhere-desktop"},
    }
    pm = {"umo_id": "01KDESKTOPNESTED00000000AA"}
    blob = umo_format.produce_umo_for_owner(payload, pm, owner_priv.public_key(), signing)
    vault.write_umo("01KDESKTOPNESTED00000000AA", "did:mi:owner-local", blob)

    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda t: [1.0, 0.0, 0.0])
    idx = indexer.build_index_from_vault(owner_priv=owner_priv)
    e = idx.get("01KDESKTOPNESTED00000000AA")
    assert e is not None, "a real nested desktop .umo must enter the index"
    assert e.summary == "we picked Postgres for billing"   # from semantic.claim
    assert e.entities == ["Postgres"]                       # from semantic.entities
    assert e.source == "somewhere-desktop"                  # from provenance.source
    assert e.created_at > 0                                  # from temporal.observed_at


def test_load_index_corrupt_returns_none(owner_env):
    # A truncated/garbage sidecar must NOT raise (would crash the read path) — degrade to None.
    p = paths.local_index_path(create=True)
    p.write_text("{ this is not valid json")
    assert indexer.load_index() is None


def test_build_does_not_crash_when_embedder_missing(owner_env, monkeypatch):
    # A vectorless .umo + no embedder must not blow up the whole build (review H4) — it
    # logs and leaves that file unindexed rather than silently producing nothing or raising.
    import mi_mcp.embedder as emb
    owner_priv = keys.load_master_private_key()
    signing = keys.load_local_signing_key()  # owner signing key (env) → passes verify
    blob = umo_format.produce_umo_for_owner(
        {"normalized_text": "text only, no vector"}, {"umo_id": "x"},
        owner_priv.public_key(), signing,
    )
    vault.write_umo("x", "did:mi:owner-local", blob)

    def _missing(_t):
        raise emb.LocalEmbedderError("fastembed not installed")
    monkeypatch.setattr("mi_mcp.embedder.embed_one", _missing)
    idx = indexer.build_index_from_vault(owner_priv=owner_priv)  # must NOT raise
    assert len(idx) == 0


def test_build_skips_vectorless_when_embed_missing_false(owner_env):
    owner_priv = keys.load_master_private_key()
    signing = keys.load_local_signing_key()  # owner signing key (env) → passes verify
    payload = {"normalized_text": "no embedding here"}
    pm = {"umo_id": "skipme", "created_at": "2026-06-20T00:00:00Z"}
    blob = umo_format.produce_umo_for_owner(payload, pm, owner_priv.public_key(), signing)
    vault.write_umo("skipme", "did:mi:owner-local", blob)
    idx = indexer.build_index_from_vault(owner_priv=owner_priv, embed_missing=False)
    assert "skipme" not in idx and len(idx) == 0


def test_incremental_add_and_remove(owner_env):
    payload = {"embedding": [1, 0, 0], "summary": "note"}
    assert indexer.add_to_index(payload, {"umo_id": "z"}) is True
    idx = indexer.load_index()
    assert idx is not None and "z" in idx

    assert indexer.remove_from_index("z") is True
    assert "z" not in indexer.load_index()
    assert indexer.remove_from_index("missing") is False


def test_build_rejects_tampered_signature(owner_env):
    # CR5: a .umo whose bytes were tampered must fail Ed25519 verify → never indexed.
    owner_priv = keys.load_master_private_key()
    signing = keys.load_local_signing_key()
    blob = bytearray(umo_format.produce_umo_for_owner(
        {"embedding": [1, 0, 0], "summary": "tamper"}, {"umo_id": "tmp"},
        owner_priv.public_key(), signing))
    blob[len(blob) - umo_format._SIG_LEN - 1] ^= 0xFF  # flip a signed byte
    vault.write_umo("tmp", "did:mi:owner-local", bytes(blob))
    assert "tmp" not in indexer.build_index_from_vault(owner_priv=owner_priv)


def test_build_rejects_wrong_signer(owner_env):
    # CR5: a forger who knows the owner's PUBLIC x25519 key can encrypt-for-owner,
    # but cannot sign as the owner → the file is rejected at index time.
    owner_priv = keys.load_master_private_key()
    attacker = ed25519.Ed25519PrivateKey.generate()  # NOT the owner's signing key
    blob = umo_format.produce_umo_for_owner(
        {"embedding": [1, 0, 0], "summary": "forged"}, {"umo_id": "forged"},
        owner_priv.public_key(), attacker)
    vault.write_umo("forged", "did:mi:owner-local", blob)
    assert "forged" not in indexer.build_index_from_vault(owner_priv=owner_priv)
    # verification OFF → it WOULD index; proves the gate is what blocks it
    assert "forged" in indexer.build_index_from_vault(owner_priv=owner_priv, verify_signature=False)
