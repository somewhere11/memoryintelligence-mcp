"""Build + persist the local vector index from the encrypted ``.umo`` vault.

This is the glue between the store (:mod:`vault`), the crypto (:mod:`umo_format` /
:mod:`keys`) and the rank (:mod:`local_index`). It reads the vault, decrypts each
``.umo`` with the owner's key, lifts the embedding + summary + entities + topics out
of the payload, and assembles a :class:`~mi_mcp.local_index.LocalIndex`. The result
is persisted to a JSON sidecar (:func:`mi_mcp.paths.local_index_path`).

Decryption happens here — building the index needs the owner key, so this is a CLI /
warm-start operation (where a Keychain unlock prompt is acceptable), not something
done on every read. The :mod:`server` read path loads the prebuilt sidecar.

AT-REST (decided 2026-06-23): **FileVault-only for v0**, encrypt-after-proof. The
sidecar holds summaries (PII) + embeddings, so it lives in the FileVault-protected
hidden trusted dir and is plaintext JSON for now. :func:`save_index` /
:func:`load_index` are the single seam through which the index is persisted, so
swapping in AES-256-GCM keyed off the owner key later is a localized change here —
nothing else in the codebase knows how the sidecar is stored.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import keys, paths, umo_format, vault
from .local_index import IndexEntry, LocalIndex

logger = logging.getLogger("mi_mcp.indexer")

# Encrypt-after-proof seam. While False, the sidecar is plaintext JSON protected by
# device full-disk encryption. Flip + implement in save_index/load_index to harden.
_ENCRYPT_SIDECAR = False


# ---------------------------------------------------------------------------
# payload → IndexEntry (pure; unit-testable without a vault)
# ---------------------------------------------------------------------------

def _entity_names(entities) -> list[str]:
    """Normalize an entities field (list of strings OR entity dicts) to names."""
    out: list[str] = []
    for e in entities or []:
        if isinstance(e, str):
            name = e
        elif isinstance(e, dict):
            name = (
                e.get("text") or e.get("name") or e.get("value")
                or e.get("entity") or e.get("canonical") or ""
            )
        else:
            name = str(e)
        if name:
            out.append(name)
    return out


def _to_epoch(value) -> float:
    """Coerce a created_at (epoch number or ISO-8601 string) to epoch seconds."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).replace("Z", "+00:00")  # fromisoformat pre-3.11 rejects 'Z'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)  # naive ISO → UTC, not machine-local
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def entry_from_payload(payload: dict, public_metadata: Optional[dict] = None) -> Optional[IndexEntry]:
    """Build an :class:`IndexEntry` from a decrypted ``.umo`` payload.

    Reads BOTH payload shapes: the MCP/backfill FLAT shape
    (``summary``/``entities``/``created_at``/``source``) and the desktop NESTED shape
    (``{semantic:{claim,entities}, temporal:{observed_at}, provenance:{source}}``) — so
    one index spans files written by either engine. Returns ``None`` when the payload
    carries no embedding (such a UMO is routed to re-embedding to enter the index).
    """
    pm = public_metadata or {}
    sem = payload.get("semantic") or {}
    prov = payload.get("provenance") or {}
    temp = payload.get("temporal") or {}
    embedding = payload.get("embedding")
    if not embedding:
        return None
    umo_id = pm.get("umo_id") or payload.get("umo_id") or ""
    if not umo_id:
        return None
    return IndexEntry(
        umo_id=umo_id,
        embedding=list(embedding),
        summary=payload.get("summary") or sem.get("claim") or "",
        entities=_entity_names(payload.get("entities") or sem.get("entities")),
        topics=list(payload.get("topics") or []),
        created_at=_to_epoch(
            payload.get("created_at") or pm.get("created_at") or temp.get("observed_at")
        ),
        source=payload.get("source") or payload.get("source_type") or prov.get("source") or "",
    )


# Fields a decrypted payload might carry the recallable text under — MCP-written
# (.umo from backfill) or desktop-written use different names.
_TEXT_FIELDS = ("normalized_text", "summary", "raw_text", "content", "content_text", "text", "body")


def _text_from_payload(payload: dict) -> str:
    """Best recallable text in a decrypted payload, whichever engine wrote it.

    Flat fields first (MCP/backfill), then the desktop's nested ``semantic.claim``.
    """
    for k in _TEXT_FIELDS:
        v = payload.get(k)
        if v and str(v).strip():
            return str(v)
    claim = (payload.get("semantic") or {}).get("claim")
    if claim and str(claim).strip():
        return str(claim)
    return ""


def _reembed_entry(payload: dict, public_metadata: Optional[dict] = None) -> Optional[IndexEntry]:
    """Build an entry for a payload with NO usable embedding by re-embedding its text
    with the canonical local model (bge-small).

    This is the intelligence-normalizer step: it lets one index span ``.umo`` written
    by engines that don't embed (e.g. the desktop's Rust engine), so the local home
    has a single vector space. Returns None if there's no text/id or the embedder is
    unavailable (graceful degrade — such a file is simply left out of the index).
    """
    text = _text_from_payload(payload)
    umo_id = (public_metadata or {}).get("umo_id") or payload.get("umo_id")
    if not text or not umo_id:
        return None
    from . import embedder  # lazy: only re-embedding needs the [local] extra
    try:
        vec = embedder.embed_one(text)
    except embedder.LocalEmbedderError:
        raise  # missing [local] extra — surface loudly to the build loop, don't silently drop
    except Exception:
        return None
    summary = payload.get("summary") or (payload.get("semantic") or {}).get("claim") or text[:200]
    enriched = {**payload, "embedding": vec, "summary": summary}
    return entry_from_payload(enriched, public_metadata)


# ---------------------------------------------------------------------------
# build from the vault (needs the owner key — decrypts each .umo)
# ---------------------------------------------------------------------------

def build_index_from_vault(
    owner_priv=None, weights: Optional[dict] = None, embed_missing: bool = True,
    verify_signature: bool = True,
) -> LocalIndex:
    """Decrypt every ``.umo`` in the vault and assemble a fresh :class:`LocalIndex`.

    Files that don't decrypt with this owner key (foreign / corrupt) are skipped —
    building is best-effort and never raises on one bad file. A file that carries no
    embedding is **re-embedded** with the canonical local model (``embed_missing``,
    default on) so desktop-written ``.umo`` enter the same vector space; set
    ``embed_missing=False`` to index only files that already carry a vector.

    SIGNATURE VERIFICATION (``verify_signature``, default on — review CR5): each
    ``.umo`` is Ed25519-verified against the owner's local signing key BEFORE it is
    decrypted or indexed, so a forged file dropped into the vault (anyone who knows
    the owner's *public* X25519 key could craft one) is rejected, not trusted and
    served to the agent. If the signing key can't be resolved, verification is
    disabled with a warning rather than failing the whole build.
    """
    if owner_priv is None:
        owner_priv = keys.load_master_private_key(create=False)

    signing_pub = None
    if verify_signature:
        try:
            signing_pub = keys.load_local_signing_key(create=False).public_key()
        except Exception as e:
            logger.warning("signature verification DISABLED — no local signing key (%s)", e)

    idx = LocalIndex(weights=weights)
    reembed_off = False  # flips once if the embedder is unavailable (don't retry per file)
    skipped = 0
    unverified = 0
    for p in vault.list_umo_files():
        try:
            parsed = umo_format.parse(p.read_bytes())
            if signing_pub is not None and not umo_format.verify(parsed, signing_pub):
                unverified += 1  # forged / foreign-signed → reject BEFORE decrypt
                continue
            payload = umo_format.decrypt_as_owner(parsed, owner_priv)
        except Exception:
            skipped += 1
            continue
        entry = entry_from_payload(payload, parsed.public_metadata)
        if entry is None and embed_missing and not reembed_off:
            try:
                entry = _reembed_entry(payload, parsed.public_metadata)
            except Exception as e:  # LocalEmbedderError — [local] extra not installed
                logger.warning(
                    "re-embed unavailable (%s) — vectorless .umo left UNINDEXED; "
                    "install memoryintelligence-mcp[local]", e,
                )
                reembed_off = True
        if entry is not None:
            idx.add(entry)
        else:
            skipped += 1
    if skipped:
        logger.info("index build: %d of %d files skipped (no vector/text, foreign key, or corrupt)",
                    skipped, len(vault.list_umo_files()))
    if unverified:
        logger.warning("index build: %d files FAILED signature verification — NOT indexed", unverified)
    return idx


# ---------------------------------------------------------------------------
# persistence — the single sidecar seam (FileVault-only v0; encrypt later)
# ---------------------------------------------------------------------------

def save_index(idx: LocalIndex, path: Optional[Path] = None) -> Path:
    path = path or paths.local_index_path(create=True)
    if _ENCRYPT_SIDECAR:  # pragma: no cover - hardening lands after v0 proof
        raise NotImplementedError("encrypted sidecar not implemented yet")
    idx.save(path)  # atomic + 0600 (LocalIndex.save)
    # The sidecar holds PII (summaries) — owner-only at rest, even before the
    # encrypt-after-proof hardening lands. Lock the file AND the dir.
    try:
        os.chmod(path, 0o600)
        os.chmod(Path(path).parent, 0o700)
    except OSError:  # pragma: no cover - non-POSIX / unusual FS
        pass
    return path


def load_index(path: Optional[Path] = None) -> Optional[LocalIndex]:
    """Load the prebuilt sidecar, or ``None`` if it doesn't exist or is unreadable.

    A corrupt / partially-written / version-incompatible sidecar returns ``None``
    (degrade to cloud or a rebuild) rather than raising — a bad sidecar must never
    crash the read path.
    """
    path = path or paths.local_index_path()
    if not Path(path).exists():
        return None
    if _ENCRYPT_SIDECAR:  # pragma: no cover - hardening lands after v0 proof
        raise NotImplementedError("encrypted sidecar not implemented yet")
    try:
        return LocalIndex.load(path)
    except Exception:
        return None


def rebuild_and_save(owner_priv=None, path: Optional[Path] = None) -> int:
    """Rebuild the index from the vault and persist it. Returns the entry count."""
    idx = build_index_from_vault(owner_priv=owner_priv)
    save_index(idx, path)
    return len(idx)


# ---------------------------------------------------------------------------
# incremental upkeep — keep the sidecar in sync on capture / forget
# ---------------------------------------------------------------------------

def add_to_index(payload: dict, public_metadata: Optional[dict] = None,
                 path: Optional[Path] = None) -> bool:
    """Add (or replace) one UMO in the persisted index. Returns True if added."""
    entry = entry_from_payload(payload, public_metadata)
    if entry is None:
        return False
    idx = load_index(path) or LocalIndex()
    idx.add(entry)
    save_index(idx, path)
    return True


def remove_from_index(umo_id: str, path: Optional[Path] = None) -> bool:
    """Drop one UMO from the persisted index. Returns True if it was present."""
    idx = load_index(path)
    if idx is None or umo_id not in idx:
        return False
    idx.remove(umo_id)
    save_index(idx, path)
    return True
