"""End-to-end tests for the local vault (Path A / key model A1).

Proves the owner-encryption loop with NO Keychain and NO network: a `.umo` is
produced encrypted for the owner's public key, written to the vault, found by
umo_id, signature-verified offline, decrypted only with the owner's private key,
and deleted. Also checks filename opacity and the ~/.mi → ~/.memoryintelligence
migration.
"""

from __future__ import annotations

import base64

import pytest

cryptography = pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519  # noqa: E402

from mi_mcp import keys, paths, umo_format, vault  # noqa: E402


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
    """An owner master key (env-injected) + a tmp vault."""
    priv = x25519.X25519PrivateKey.generate()
    monkeypatch.setenv("MI_MASTER_KEY", _raw_priv_b64(priv))
    monkeypatch.setenv("MI_VAULT", str(tmp_path / "vault"))
    return priv


def test_master_key_loads_from_env(owner_env):
    loaded = keys.load_master_private_key()
    assert keys.public_key_b64(loaded) == keys.public_key_b64(owner_env)


def test_full_roundtrip(owner_env):
    owner_priv = keys.load_master_private_key()
    owner_pub = owner_priv.public_key()
    signing = ed25519.Ed25519PrivateKey.generate()  # stand-in for MI's signing key

    payload = {"semantic": {"subject": "we", "verb": "chose", "object": "Postgres"},
               "note": "needed transactions"}
    pm = {"umo_id": "01HXTESTULID0000000000000A", "owner_did": "did:mi:tester",
          "created_at": "2026-06-05T00:00:00Z", "content_type": "decision"}

    blob = umo_format.produce_umo_for_owner(payload, pm, owner_pub, signing)

    # write to vault
    path = vault.write_umo(pm["umo_id"], pm["owner_did"], blob)
    assert path.exists()

    # opaque filename — no ULID, no timestamp leak
    assert pm["umo_id"] not in path.name
    assert path.name == vault.umo_filename(pm["umo_id"], pm["owner_did"])
    assert len(path.stem) == 16

    # list + find + summarize work off plaintext metadata (no key)
    assert path in vault.list_umo_files()
    assert vault.find_by_umo_id(pm["umo_id"]) == path
    rows = vault.summarize()
    assert rows and rows[0]["umo_id"] == pm["umo_id"] and rows[0]["created_at"] == pm["created_at"]

    # verify offline against the signing public key
    parsed = umo_format.parse(blob)
    assert umo_format.verify(parsed, signing.public_key()) is True

    # decrypt only with the owner's private key
    out = umo_format.decrypt_as_owner(parsed, owner_priv)
    assert out == payload

    # delete
    assert vault.delete_umo(pm["umo_id"]) is True
    assert vault.find_by_umo_id(pm["umo_id"]) is None


def test_a_different_key_cannot_decrypt(owner_env):
    owner_pub = keys.load_master_private_key().public_key()
    signing = ed25519.Ed25519PrivateKey.generate()
    pm = {"umo_id": "01HXOTHER0000000000000000B", "owner_did": "did:mi:tester"}
    blob = umo_format.produce_umo_for_owner({"x": 1}, pm, owner_pub, signing)
    parsed = umo_format.parse(blob)

    attacker = x25519.X25519PrivateKey.generate()
    with pytest.raises(Exception):
        umo_format.decrypt_as_owner(parsed, attacker)


def test_tamper_breaks_signature(owner_env):
    owner_pub = keys.load_master_private_key().public_key()
    signing = ed25519.Ed25519PrivateKey.generate()
    pm = {"umo_id": "01HXTAMPER000000000000000C", "owner_did": "did:mi:tester"}
    blob = bytearray(umo_format.produce_umo_for_owner({"x": 1}, pm, owner_pub, signing))
    # flip a byte in the opaque payload region (still signed, but keeps the
    # envelope parseable so it's verify() — not parse() — that catches it)
    blob[len(blob) - umo_format._SIG_LEN - 1] ^= 0xFF
    parsed = umo_format.parse(bytes(blob))
    assert umo_format.verify(parsed, signing.public_key()) is False


def test_filename_is_deterministic_and_opaque():
    a = vault.umo_filename("01HX", "did:mi:x")
    b = vault.umo_filename("01HX", "did:mi:x")
    c = vault.umo_filename("01HX", "did:mi:y")
    assert a == b and a != c
    assert a.endswith(".umo") and "01HX" not in a


def test_opt_in_migration(tmp_path, monkeypatch):
    # redirect both ~ and the hidden home into tmp
    monkeypatch.setattr(paths, "_home", lambda: tmp_path)
    monkeypatch.delenv("MI_HOME", raising=False)
    legacy = tmp_path / ".mi"
    legacy.mkdir()
    (legacy / "opt-in-paths").write_text("/Users/x/project\n")

    # new location absent → fallback resolves to legacy
    assert paths.opt_in_paths_file() == legacy / "opt-in-paths"

    # migrate forward (non-destructive copy)
    assert paths.migrate_opt_in_forward() is True
    new = tmp_path / ".memoryintelligence" / "mcp" / "opt-in-paths"
    assert new.exists() and new.read_text() == "/Users/x/project\n"
    assert legacy.exists()  # legacy left intact
    assert paths.opt_in_paths_file() == new  # now prefers new
