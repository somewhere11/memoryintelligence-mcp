"""The local ``.umo`` vault — ``~/MemoryIntelligence/`` (relocatable via ``MI_VAULT``).

Files are named by an **opaque hash** (locked 2026-06-05):
``sha256(umo_id : owner_did)[:16].umo`` — so a directory listing or watcher log
leaks no capture timestamps (unlike a raw ULID filename). Lookup by ``umo_id``
scans the plaintext public-metadata blocks (no key needed), so the opaque name
never blocks finding a memory.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from . import paths, umo_format

SUFFIX = ".umo"


def vault_path(create: bool = False) -> Path:
    return paths.vault_dir(create=create)


def umo_filename(umo_id: str, owner_did: str) -> str:
    """``sha256(umo_id ':' owner_did)[:16].umo`` — opaque, no timestamp leak."""
    digest = hashlib.sha256(f"{umo_id}:{owner_did}".encode()).hexdigest()[:16]
    return f"{digest}{SUFFIX}"


def write_umo(umo_id: str, owner_did: str, blob: bytes) -> Path:
    """Write a ``.umo`` blob into the vault atomically. Returns the file path."""
    d = vault_path(create=True)
    dest = d / umo_filename(umo_id, owner_did)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, dest)  # atomic
    return dest


def list_umo_files() -> list[Path]:
    d = vault_path()
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.suffix == SUFFIX and p.is_file())


def find_by_umo_id(umo_id: str) -> Path | None:
    """Locate a vault file by its ``umo_id`` (reads only plaintext public metadata)."""
    for p in list_umo_files():
        try:
            parsed = umo_format.parse(p.read_bytes())
        except Exception:
            continue
        if parsed.umo_id == umo_id:
            return p
    return None


def delete_umo(umo_id: str) -> bool:
    """Delete a memory's file by ``umo_id``. Returns True if a file was removed."""
    p = find_by_umo_id(umo_id)
    if p is None:
        return False
    p.unlink()
    return True


def summarize() -> list[dict]:
    """Lightweight listing from plaintext metadata only (no decryption)."""
    out = []
    for p in list_umo_files():
        row = {"file": p.name, "size": p.stat().st_size, "umo_id": "?", "created_at": "?"}
        try:
            pm = umo_format.parse(p.read_bytes()).public_metadata
            row["umo_id"] = pm.get("umo_id", "?")
            row["created_at"] = pm.get("created_at", "?")
        except Exception:
            row["umo_id"] = "(unreadable)"
        out.append(row)
    return out
