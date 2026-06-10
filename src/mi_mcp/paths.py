"""Filesystem layout for Memory Intelligence (locked 2026-06-05).

One brand namespace, clear visibility split — no lookalike names:

  ~/MemoryIntelligence/          visible vault: the user's *.umo files (relocatable via MI_VAULT)
  ~/.memoryintelligence/mcp/     hidden MCP config (opt-in-paths, launcher)
  ~/.memoryintelligence/sdk/     hidden SDK plumbing (models, cache)
  OS Keychain                    keys (never on disk)

Retires the legacy ``~/.mi/`` config dir: path resolution prefers the new
location but falls back to ``~/.mi/`` for one release so existing wiring keeps
working. Nothing is moved destructively — the launcher relocates on the next
``mi-mcp wire``; only the opt-in allowlist is (non-destructively) copied forward.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

HIDDEN_HOME_ENV = "MI_HOME"   # override the hidden plumbing home
VAULT_ENV = "MI_VAULT"        # override the visible vault location


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def hidden_home() -> Path:
    """``~/.memoryintelligence`` (or ``$MI_HOME``)."""
    override = os.environ.get(HIDDEN_HOME_ENV)
    return Path(override).expanduser() if override else _home() / ".memoryintelligence"


def mcp_config_dir(create: bool = False) -> Path:
    d = hidden_home() / "mcp"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def sdk_dir(create: bool = False) -> Path:
    d = hidden_home() / "sdk"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def legacy_mcp_dir() -> Path:
    """The retired ``~/.mi/`` directory."""
    return _home() / ".mi"


def vault_dir(create: bool = False) -> Path:
    """The visible ``~/MemoryIntelligence/`` vault (or ``$MI_VAULT``)."""
    override = os.environ.get(VAULT_ENV)
    d = Path(override).expanduser() if override else _home() / "MemoryIntelligence"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def opt_in_paths_file() -> Path:
    """The capture-consent allowlist. New location preferred; falls back to the
    legacy ``~/.mi/opt-in-paths`` if it exists and the new one doesn't."""
    new = mcp_config_dir() / "opt-in-paths"
    if new.exists():
        return new
    legacy = legacy_mcp_dir() / "opt-in-paths"
    if legacy.exists():
        return legacy
    return new  # default to the new location for writes


def migrate_opt_in_forward() -> bool:
    """Non-destructively copy the legacy opt-in allowlist to the new location if
    the new one doesn't exist yet. Leaves ``~/.mi/`` intact (the launcher there
    keeps working until the next ``mi-mcp wire``). Returns True if it copied."""
    new = mcp_config_dir() / "opt-in-paths"
    legacy = legacy_mcp_dir() / "opt-in-paths"
    if new.exists() or not legacy.exists():
        return False
    new.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, new)
    return True
