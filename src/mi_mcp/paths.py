"""Filesystem layout for MemoryIntelligence — one on-brand namespace.

Single visible/hidden split, no lookalike names:

  ~/MemoryIntelligence/          visible vault: the user's *.umo files (relocatable via MI_VAULT)
  ~/.memoryintelligence/mcp/     hidden MCP config — launcher + capture opt-in allowlist
  ~/.memoryintelligence/sdk/     hidden SDK plumbing (models, cache)
  ~/.memoryintelligence/.env     on-disk keyfile (chmod 600) — cross-platform fallback to the Keychain
  OS Keychain                    keys, preferred (never on disk)

As of 0.1.7 ``mi-mcp setup``/``wire`` write this layout directly. The retired
``~/.mi/`` config dir and ``~/.mi-env`` keyfile are still *read* (one-release
fallback) so existing installs keep working until the next ``wire``; nothing is
moved destructively. The opt-in allowlist is copied forward on ``wire``.

Every resolver takes an optional ``home`` (used by the CLI's ``--home`` test
flag and to keep read/write paths in lockstep); when ``None`` it resolves from
``$MI_HOME`` then ``~``. This module is the SINGLE source of truth for the
layout — the CLI and the server's consent gate both call it.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

HIDDEN_HOME_ENV = "MI_HOME"   # override the hidden plumbing home
VAULT_ENV = "MI_VAULT"        # override the visible vault location


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _base(home: Path | None) -> Path:
    """The home under which the layout is rooted. An explicit ``home`` (CLI
    ``--home``) wins; else ``~``. ``$MI_HOME`` overrides only the hidden tree."""
    return Path(home) if home is not None else _home()


def hidden_home(home: Path | None = None) -> Path:
    """``~/.memoryintelligence`` (or ``$MI_HOME``, or ``<home>/.memoryintelligence``)."""
    if home is not None:
        return Path(home) / ".memoryintelligence"
    override = os.environ.get(HIDDEN_HOME_ENV)
    return Path(override).expanduser() if override else _home() / ".memoryintelligence"


def mcp_config_dir(create: bool = False, home: Path | None = None) -> Path:
    d = hidden_home(home) / "mcp"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def sdk_dir(create: bool = False, home: Path | None = None) -> Path:
    d = hidden_home(home) / "sdk"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def legacy_mcp_dir(home: Path | None = None) -> Path:
    """The retired ``~/.mi/`` directory (read-only fallback)."""
    return _base(home) / ".mi"


def vault_dir(create: bool = False, home: Path | None = None) -> Path:
    """The visible ``~/MemoryIntelligence/`` vault (or ``$MI_VAULT``)."""
    override = os.environ.get(VAULT_ENV)
    if override:
        d = Path(override).expanduser()
    else:
        d = _base(home) / "MemoryIntelligence"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def wrapper_path(create: bool = False, home: Path | None = None) -> Path:
    """The launch wrapper (``run-mi-mcp.sh``) that resolves MI_API_KEY at spawn."""
    return mcp_config_dir(create=create, home=home) / "run-mi-mcp.sh"


def local_index_path(create: bool = False, home: Path | None = None) -> Path:
    """The local vector-index sidecar (``~/.memoryintelligence/mcp/local_index.json``).

    Lives in the hidden trusted dir alongside the rest of the MCP plumbing. The
    sidecar holds summaries (PII) + embeddings, so it relies on device full-disk
    encryption (FileVault — also the school-tier install requirement) at rest for
    v0; encrypting it with the owner key is the next hardening (see ``indexer.py``).
    """
    return mcp_config_dir(create=create, home=home) / "local_index.json"


def keyfile_path(home: Path | None = None) -> Path:
    """Preferred on-disk keyfile (``~/.memoryintelligence/.env``, chmod 600) — the
    cross-platform fallback when there is no Keychain. Shared by mcp + sdk."""
    return hidden_home(home) / ".env"


def legacy_keyfile_path(home: Path | None = None) -> Path:
    """The retired ``~/.mi-env`` keyfile, still read for back-compat (and the
    ecosystem digest pipeline that points at it)."""
    return _base(home) / ".mi-env"


def resolve_keyfile(home: Path | None = None) -> Path | None:
    """Existing keyfile to read — new location preferred, legacy fallback — or
    ``None`` if neither exists (then only env/Keychain can supply the key)."""
    for p in (keyfile_path(home), legacy_keyfile_path(home)):
        if p.exists():
            return p
    return None


def opt_in_paths_file(home: Path | None = None) -> Path:
    """The capture-consent allowlist. New location preferred; falls back to the
    legacy ``~/.mi/opt-in-paths`` if it exists and the new one doesn't."""
    new = mcp_config_dir(home=home) / "opt-in-paths"
    if new.exists():
        return new
    legacy = legacy_mcp_dir(home) / "opt-in-paths"
    if legacy.exists():
        return legacy
    return new  # default to the new location for writes


def migrate_opt_in_forward(home: Path | None = None) -> bool:
    """Non-destructively copy the legacy opt-in allowlist to the new location if
    the new one doesn't exist yet. Leaves ``~/.mi/`` intact. Returns True if it
    copied."""
    new = mcp_config_dir(home=home) / "opt-in-paths"
    legacy = legacy_mcp_dir(home) / "opt-in-paths"
    if new.exists() or not legacy.exists():
        return False
    new.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, new)
    return True
