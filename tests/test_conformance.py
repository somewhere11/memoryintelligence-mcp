"""Cross-surface .umo conformance — Python against the SHARED golden fixture.

`tests/fixtures/golden.umo` is the canonical `.umo` the desktop's Rust codec validates
against in `crates/umo/tests/conformance.rs`. Decrypting + verifying it here proves the
Python codec agrees with the Rust codec on the byte format AND the (nested) payload
schema — the cross-language drift guard that was missing (review finding CR2/C2). The
owner seed and MI public key are the documented, non-secret test vectors.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

cryptography = pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.asymmetric import ed25519, x25519  # noqa: E402

from mi_mcp import indexer, umo_format  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
OWNER_SEED = bytes([0x42] * 32)  # documented test seed (NOT secret); matches Rust conformance.rs


def _golden():
    return umo_format.parse((FIX / "golden.umo").read_bytes())


def test_python_reads_shared_golden_umo():
    parsed = _golden()
    assert parsed.format_version == 0x0100
    assert [s.slot_id for s in parsed.key_slots] == ["owner"]

    # signature verifies against the pinned MI public key (the same fixture Rust checks)
    mi_pub = ed25519.Ed25519PublicKey.from_public_bytes(
        base64.b64decode((FIX / "mi_public_key.b64").read_text().strip())
    )
    assert umo_format.verify(parsed, mi_pub) is True

    # only the owner key decrypts, and the payload byte-matches the committed expectation
    owner = x25519.X25519PrivateKey.from_private_bytes(OWNER_SEED)
    payload = umo_format.decrypt_as_owner(parsed, owner)
    assert payload == json.loads((FIX / "expected_payload.json").read_text())


def test_wrong_owner_key_cannot_decrypt_golden():
    parsed = _golden()
    wrong = x25519.X25519PrivateKey.from_private_bytes(bytes([7] * 32))
    with pytest.raises(Exception):
        umo_format.decrypt_as_owner(parsed, wrong)


def test_indexer_reads_the_real_nested_desktop_payload(monkeypatch):
    # The golden payload is the REAL desktop nested shape ({semantic, temporal, provenance}),
    # not a hand-built flat one. It has no embedding → the re-embed path must extract the
    # claim text and lift summary/source from the nested keys.
    parsed = _golden()
    owner = x25519.X25519PrivateKey.from_private_bytes(OWNER_SEED)
    payload = umo_format.decrypt_as_owner(parsed, owner)

    assert "semantic" in payload and "embedding" not in payload  # nested, vectorless
    assert indexer.entry_from_payload(payload, parsed.public_metadata) is None  # no vector → re-embed

    monkeypatch.setattr("mi_mcp.embedder.embed_one", lambda t: [1.0, 0.0, 0.0])
    entry = indexer._reembed_entry(payload, parsed.public_metadata)
    assert entry is not None
    assert "owner-only decryption" in entry.summary           # from semantic.claim
    assert entry.source == "desktop-app-design/spike"          # from provenance.source
    assert entry.embedding == [1.0, 0.0, 0.0]
