"""The ``.umo`` envelope — canonical FEAT-0051 **v1.0 (0x0100)** layout.

Parse / verify / decrypt-as-owner, plus a reference producer that stands in for
the server-side serializer (W1) until it's built — producing byte-identical files.

Binary layout (§5 of the format spec), big-endian:
  0x0000  4   magic            0x554D4F21 ("UMO!")
  0x0004  2   format_version   uint16 (0x0100)
  0x0006  4   metadata_len     uint32
  0x000A  n   public_metadata  UTF-8 JSON, plaintext
  —       2   key_slot_count   uint16
  —       n   key_slots[]      one per reader (binary, see _encode_slot)
  —       12  gcm_iv           AES-256-GCM nonce, plaintext
  —       4   payload_len      uint32
  —       n   encrypted_payload AES-256-GCM ciphertext (semantic+temporal+provenance)
  —       16  gcm_auth_tag     GCM tag
  EOF-64  64  mi_signature     Ed25519 over all preceding bytes

Key model: per-UMO CEK (AES-256-GCM). The owner slot wraps the CEK via X25519
ECDH → HKDF-SHA256 → AES-256 key-wrap. NB: for server-side (Path A) capture the
"owner" uses the X25519 ECDH path — the spec's symmetric Master-Key path only
works client-side (the server can't wrap with a key it never holds), so the owner
is "a reader of their own data" via the slot's ``owner_ephemeral_pubkey`` field.

Requires the ``[local]`` extra (``cryptography``); imported lazily.
"""

from __future__ import annotations

import base64
import json
import os
import struct
from dataclasses import dataclass

MAGIC = b"UMO!"  # 0x554D4F21
FORMAT_VERSION = 0x0100  # canonical FEAT-0051 v1.0

# Shared cross-surface .umo conventions. The Rust desktop app ("Somewhere") writes
# these same values, so a file written by the MCP and one written by the desktop
# are mutually READABLE — but only when both surfaces point at the SAME directory.
# By default they do NOT: mi-mcp resolves ~/MemoryIntelligence while the desktop
# reads ~/Somewhere (#653), so identical conventions in two dirs are two vaults,
# not one. `mi-mcp wire` bakes MI_VAULT=~/Somewhere into its launcher to unify them.
# owner_did is a plaintext metadata label only (NOT used in decryption — that's the
# X25519 key), so a fixed value is safe and keeps the conventions consistent.
LOCAL_OWNER_DID = "did:mi:owner-local"
FORMAT_VERSION_STR = "0x0100"  # string form the desktop stores in public_metadata
_HKDF_INFO = b"umo-cek-wrap-v1"
_SIG_LEN = 64
_IV_LEN = 12
_TAG_LEN = 16
_SCOPE_ALL = 0xFF


class UMOFormatError(Exception):
    pass


def _crypto():
    try:
        from cryptography.hazmat.primitives import hashes  # noqa: F401
        from cryptography.hazmat.primitives.asymmetric import ed25519, x25519  # noqa: F401
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: F401
        from cryptography.hazmat.primitives.keywrap import (  # noqa: F401
            aes_key_unwrap, aes_key_wrap,
        )
    except ImportError as e:  # pragma: no cover
        raise UMOFormatError(
            "Local vault crypto needs 'cryptography'. Install: "
            "pip install 'memoryintelligence-mcp[local]'"
        ) from e


@dataclass
class KeySlot:
    slot_id: str
    scope_flags: int
    expires_at: int                # unix ts; 0 = no expiry
    ephemeral_pubkey: bytes        # X25519 raw (32)
    wrapped_cek: bytes             # AES-256-KW output


@dataclass
class ParsedUMO:
    format_version: int
    public_metadata: dict
    key_slots: list                # list[KeySlot]
    gcm_iv: bytes
    ciphertext: bytes
    auth_tag: bytes
    signature: bytes
    signed_bytes: bytes

    @property
    def umo_id(self) -> str:
        return self.public_metadata.get("umo_id", "")


# ---------------------------------------------------------------------------
# encoding helpers
# ---------------------------------------------------------------------------

def _encode_slot(s: KeySlot) -> bytes:
    sid = s.slot_id.encode()
    if len(sid) > 255:
        raise UMOFormatError("slot_id too long")
    if len(s.ephemeral_pubkey) != 32:
        raise UMOFormatError("ephemeral_pubkey must be 32 bytes")
    return b"".join([
        struct.pack(">B", len(sid)), sid,
        struct.pack(">B", s.scope_flags & 0xFF),
        struct.pack(">Q", s.expires_at),
        s.ephemeral_pubkey,
        struct.pack(">H", len(s.wrapped_cek)), s.wrapped_cek,
    ])


def _decode_slot(buf: bytes, o: int) -> tuple[KeySlot, int]:
    (sid_len,) = struct.unpack(">B", buf[o:o + 1])
    o += 1
    slot_id = buf[o:o + sid_len].decode()
    o += sid_len
    (scope,) = struct.unpack(">B", buf[o:o + 1])
    o += 1
    (exp,) = struct.unpack(">Q", buf[o:o + 8])
    o += 8
    epk = buf[o:o + 32]
    o += 32
    (wl,) = struct.unpack(">H", buf[o:o + 2])
    o += 2
    wrapped = buf[o:o + wl]
    o += wl
    return KeySlot(slot_id, scope, exp, epk, wrapped), o


def _hkdf_wrap_key(shared: bytes, umo_id: str) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return HKDF(
        algorithm=hashes.SHA256(), length=32,
        salt=umo_id.encode(), info=_HKDF_INFO,
    ).derive(shared)


# ---------------------------------------------------------------------------
# Producer (reference for the server-side serializer; used in tests)
# ---------------------------------------------------------------------------

def produce_umo_for_owner(
    payload: dict,
    public_metadata: dict,
    owner_public_key,
    signing_private_key,
) -> bytes:
    """Build a signed v1.0 ``.umo`` encrypted **for the owner's X25519 public key**.

    Exactly what the server (W1) must emit: wrap the CEK for the public key the
    owner sent on capture; only the owner's private key decrypts; Ed25519-sign
    with MI's signing key (``signing_private_key`` stands in for it).
    """
    _crypto()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.keywrap import aes_key_wrap

    umo_id = public_metadata.get("umo_id")
    if not umo_id:
        raise UMOFormatError("public_metadata must include 'umo_id'")

    # 1. encrypt payload under a fresh CEK; split GCM ct/tag per the layout
    cek = os.urandom(32)
    iv = os.urandom(_IV_LEN)
    sealed = AESGCM(cek).encrypt(iv, json.dumps(payload, separators=(",", ":")).encode(), None)
    ciphertext, auth_tag = sealed[:-_TAG_LEN], sealed[-_TAG_LEN:]

    # 2. wrap the CEK for the owner (ECDH → HKDF → AES-KW)
    eph = x25519.X25519PrivateKey.generate()
    wrap_key = _hkdf_wrap_key(eph.exchange(owner_public_key), umo_id)
    eph_pub = eph.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    )
    owner_slot = KeySlot("owner", _SCOPE_ALL, 0, eph_pub, aes_key_wrap(wrap_key, cek))

    # 3. assemble + sign
    pm = json.dumps(public_metadata, separators=(",", ":")).encode()
    slots = _encode_slot(owner_slot)
    body = b"".join([
        MAGIC, struct.pack(">H", FORMAT_VERSION),
        struct.pack(">I", len(pm)), pm,
        struct.pack(">H", 1), slots,            # key_slot_count = 1
        iv,
        struct.pack(">I", len(ciphertext)), ciphertext,
        auth_tag,
    ])
    return body + signing_private_key.sign(body)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def parse(blob: bytes) -> ParsedUMO:
    if len(blob) < 10 or blob[:4] != MAGIC:
        raise UMOFormatError("not a .umo file (bad magic)")
    ver = struct.unpack(">H", blob[4:6])[0]
    if ver != FORMAT_VERSION:
        raise UMOFormatError(
            f"unsupported format_version 0x{ver:04X} (this build reads 0x{FORMAT_VERSION:04X})"
        )
    o = 6
    (mlen,) = struct.unpack(">I", blob[o:o + 4])
    o += 4
    pm = blob[o:o + mlen]
    o += mlen
    (slot_count,) = struct.unpack(">H", blob[o:o + 2])
    o += 2
    slots = []
    for _ in range(slot_count):
        slot, o = _decode_slot(blob, o)
        slots.append(slot)
    gcm_iv = blob[o:o + _IV_LEN]
    o += _IV_LEN
    (plen,) = struct.unpack(">I", blob[o:o + 4])
    o += 4
    ciphertext = blob[o:o + plen]
    o += plen
    auth_tag = blob[o:o + _TAG_LEN]
    o += _TAG_LEN
    signed_bytes = blob[:o]
    signature = blob[o:o + _SIG_LEN]
    if len(signature) != _SIG_LEN:
        raise UMOFormatError("truncated signature")
    return ParsedUMO(
        format_version=ver, public_metadata=json.loads(pm), key_slots=slots,
        gcm_iv=gcm_iv, ciphertext=ciphertext, auth_tag=auth_tag,
        signature=signature, signed_bytes=signed_bytes,
    )


def verify(parsed: ParsedUMO, mi_public_key) -> bool:
    """Verify the Ed25519 signature against the pinned MI public key. Offline."""
    _crypto()
    from cryptography.exceptions import InvalidSignature

    try:
        mi_public_key.verify(parsed.signature, parsed.signed_bytes)
        return True
    except InvalidSignature:
        return False


def decrypt_as_owner(parsed: ParsedUMO, owner_private_key) -> dict:
    """Unwrap the CEK with the owner's X25519 key and decrypt the payload. Offline."""
    _crypto()
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.keywrap import aes_key_unwrap

    slot = next((s for s in parsed.key_slots if s.slot_id == "owner"), None)
    if slot is None:
        raise UMOFormatError("no owner key slot in this .umo")

    eph_pub = x25519.X25519PublicKey.from_public_bytes(slot.ephemeral_pubkey)
    wrap_key = _hkdf_wrap_key(owner_private_key.exchange(eph_pub), parsed.umo_id)
    cek = aes_key_unwrap(wrap_key, slot.wrapped_cek)
    pt = AESGCM(cek).decrypt(parsed.gcm_iv, parsed.ciphertext + parsed.auth_tag, None)
    return json.loads(pt)


def slot_as_dict(s: KeySlot) -> dict:
    """For display/debug — base64 the binary fields."""
    return {
        "slot_id": s.slot_id, "scope_flags": f"0x{s.scope_flags:02X}",
        "expires_at": s.expires_at,
        "epk": base64.b64encode(s.ephemeral_pubkey).decode(),
        "wrapped_cek": base64.b64encode(s.wrapped_cek).decode(),
    }
