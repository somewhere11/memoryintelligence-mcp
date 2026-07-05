"""Owner key handling for the local vault — key model **A1** (locked 2026-06-05).

The owner holds an **X25519 private key**; Memory Intelligence only ever sees the
**public key** (sent on capture). MI wraps each per-UMO content key for that
public key, so **MI cannot decrypt the owner's ``.umo`` files**.

Private-key resolution order (mirrors the API-key launcher):
  1. env ``MI_MASTER_KEY``        — base64 of the 32-byte raw private key (tests/CI/non-mac)
  2. macOS Keychain               — ``security find-generic-password -s MI_MASTER_KEY``
  3. generate a new key + store it in the Keychain (macOS); else raise.

Requires the ``[local]`` extra (``cryptography``). Imported lazily so the base
install stays thin.
"""

from __future__ import annotations

import base64
import hashlib
import os
import subprocess
from typing import Any

MASTER_KEY_ENV = "MI_MASTER_KEY"
KEYCHAIN_SERVICE = "MI_MASTER_KEY"

# Owner-held Ed25519 key used to SELF-SIGN locally-produced .umo files (backfill).
# Distinct from MI's attestation key: a backfilled record is owner-self-signed, NOT
# MI-attested — there is no way to forge an MI signature locally (we never hold MI's
# private key). Resolution mirrors the master key: env → Keychain → generate+store.
SIGNING_KEY_ENV = "MI_LOCAL_SIGNING_KEY"
SIGNING_KEYCHAIN_SERVICE = "MI_LOCAL_SIGNING_KEY"


class KeyError_(Exception):
    """Raised when the owner master key can't be resolved or created."""


def _require_crypto() -> Any:
    try:
        from cryptography.hazmat.primitives.asymmetric import x25519  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on install extras
        raise KeyError_(
            "Local vault crypto needs the 'cryptography' package. Install the "
            "local extra:  pip install 'memoryintelligence-mcp[local]'"
        ) from e
    from cryptography.hazmat.primitives.asymmetric import x25519

    return x25519


def _keychain_account() -> str:
    return os.environ.get("MI_KEYCHAIN_ACCOUNT") or os.environ.get("USER") or "default"


def _keychain_get(service: str = KEYCHAIN_SERVICE) -> str | None:
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", _keychain_account(),
             "-s", service, "-w"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _keychain_set(b64_priv: str, service: str = KEYCHAIN_SERVICE) -> bool:
    try:
        r = subprocess.run(
            ["security", "add-generic-password", "-a", _keychain_account(),
             "-s", service, "-w", b64_priv, "-U"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def _priv_from_b64(b64_priv: str):
    x25519 = _require_crypto()
    raw = base64.b64decode(b64_priv)
    if len(raw) != 32:
        raise KeyError_("MI_MASTER_KEY must be base64 of a 32-byte X25519 private key")
    return x25519.X25519PrivateKey.from_private_bytes(raw)


def _priv_to_b64(priv) -> str:
    from cryptography.hazmat.primitives import serialization

    raw = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(raw).decode()


def load_master_private_key(*, create: bool = True):
    """Return the owner's X25519 private key, creating + storing one if needed."""
    x25519 = _require_crypto()

    env = os.environ.get(MASTER_KEY_ENV)
    if env:
        return _priv_from_b64(env)

    kc = _keychain_get()
    if kc:
        return _priv_from_b64(kc)

    if not create:
        raise KeyError_("no master key found (set MI_MASTER_KEY or run on macOS)")

    priv = x25519.X25519PrivateKey.generate()
    if not _keychain_set(_priv_to_b64(priv)):
        raise KeyError_(
            "generated a master key but could not store it in the Keychain. "
            "On non-macOS, set MI_MASTER_KEY to a persisted base64 key instead."
        )
    return priv


def public_key_b64(priv=None) -> str:
    """Base64 of the 32-byte raw X25519 public key — this is what's sent to MI."""
    from cryptography.hazmat.primitives import serialization

    if priv is None:
        priv = load_master_private_key()
    raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode()


def owner_did(priv=None) -> str:
    """A stable owner identifier derived from the master public key.

    Used only to namespace vault filenames (``sha256(umo_id:owner_did)``), so it
    must be *stable per owner* — deriving it from the public key keeps re-running
    backfill idempotent (same ``umo_id`` + ``owner_did`` → same opaque filename →
    overwrite, never duplicate). It is NOT a registered DID; it never leaves the
    device.
    """
    from cryptography.hazmat.primitives import serialization

    if priv is None:
        priv = load_master_private_key()
    raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return "did:mi:key:" + hashlib.sha256(raw).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Owner self-signing key (Ed25519) — for locally-produced .umo (backfill)
# ---------------------------------------------------------------------------

def _require_ed25519() -> Any:
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on install extras
        raise KeyError_(
            "Local vault crypto needs the 'cryptography' package. Install the "
            "local extra:  pip install 'memoryintelligence-mcp[local]'"
        ) from e
    from cryptography.hazmat.primitives.asymmetric import ed25519

    return ed25519


def _ed_priv_from_b64(b64_priv: str):
    ed25519 = _require_ed25519()
    raw = base64.b64decode(b64_priv)
    if len(raw) != 32:
        raise KeyError_("MI_LOCAL_SIGNING_KEY must be base64 of a 32-byte Ed25519 seed")
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def _ed_priv_to_b64(priv) -> str:
    from cryptography.hazmat.primitives import serialization

    raw = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(raw).decode()


def load_local_signing_key(*, create: bool = True):
    """Return the owner's Ed25519 self-signing key, creating + storing one if needed.

    This signs backfill-produced ``.umo`` files. It is the owner's own key, kept
    in the Keychain alongside the master key — never MI's attestation key. Verify
    such files against :func:`local_signing_public_key_b64`.
    """
    ed25519 = _require_ed25519()

    env = os.environ.get(SIGNING_KEY_ENV)
    if env:
        return _ed_priv_from_b64(env)

    kc = _keychain_get(SIGNING_KEYCHAIN_SERVICE)
    if kc:
        return _ed_priv_from_b64(kc)

    if not create:
        raise KeyError_("no local signing key found (set MI_LOCAL_SIGNING_KEY or run on macOS)")

    priv = ed25519.Ed25519PrivateKey.generate()
    if not _keychain_set(_ed_priv_to_b64(priv), SIGNING_KEYCHAIN_SERVICE):
        raise KeyError_(
            "generated a signing key but could not store it in the Keychain. "
            "On non-macOS, set MI_LOCAL_SIGNING_KEY to a persisted base64 key instead."
        )
    return priv


def local_signing_public_key_b64(priv=None) -> str:
    """Base64 of the 32-byte raw Ed25519 public key for owner-self-signed .umo."""
    from cryptography.hazmat.primitives import serialization

    if priv is None:
        priv = load_local_signing_key()
    raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode()
