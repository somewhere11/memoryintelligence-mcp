"""Configuration for the MI MCP Server.

All config is resolved from environment variables at startup.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

from . import paths


@dataclass(frozen=True)
class MIConfig:
    """Immutable configuration resolved from environment."""

    # Required
    api_key: str

    # API endpoint (defaults to production)
    base_url: str = "https://api.memoryintelligence.io"

    # Optional defaults
    default_scope: str = "user"
    default_source: str = "mcp"  # provenance label stamped on captures lacking an explicit source
    default_retention: str = "meaning_only"
    default_pii_handling: str = "extract_and_redact"

    # Transport
    transport: str = "stdio"
    host: str = "127.0.0.1"  # loopback only; network transports are not part of v0
    port: int = 8100

    # Tool surface — v0 exposes 3 tools by default; MI_MCP_FULL=1 exposes all 10 (#256).
    full_tools: bool = False

    @classmethod
    def from_env(cls) -> MIConfig:
        """Build config from environment variables.

        Required:
            MI_API_KEY — your MemoryIntelligence API key

        Optional:
            MI_BASE_URL        — API base URL (default: https://api.memoryintelligence.io)
            MI_DEFAULT_SCOPE   — default governance scope (default: user)
            MI_TRANSPORT       — stdio | sse | streamable-http (default: stdio)
            MI_HOST            — bind host for SSE/HTTP (default: 127.0.0.1, loopback only)
            MI_PORT            — bind port for SSE/HTTP (default: 8100)
            MI_MCP_FULL        — "1" exposes all 10 tools; otherwise only the core set (#256)
        """
        api_key = os.environ.get("MI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "MI_API_KEY is required.\n"
                "Recommended: run `mi-mcp wire` — it resolves the key from your macOS Keychain\n"
                "at launch, so the key never lives in any config file. Or export MI_API_KEY in\n"
                "your shell. Never paste the key into an MCP client config file.\n"
                "Get your key at https://memoryintelligence.io/portal"
            )

        return cls(
            api_key=api_key,
            base_url=os.environ.get("MI_BASE_URL", cls.base_url).rstrip("/"),
            default_scope=os.environ.get("MI_DEFAULT_SCOPE", cls.default_scope),
            default_source=os.environ.get("MI_DEFAULT_SOURCE", cls.default_source),
            default_retention=os.environ.get("MI_DEFAULT_RETENTION", cls.default_retention),
            default_pii_handling=os.environ.get("MI_DEFAULT_PII_HANDLING", cls.default_pii_handling),
            transport=os.environ.get("MI_TRANSPORT", cls.transport),
            host=os.environ.get("MI_HOST", cls.host),
            port=int(os.environ.get("MI_PORT", str(cls.port))),
            full_tools=os.environ.get("MI_MCP_FULL") == "1",
        )


# =============================================================================
# Capture consent gate (Story 8) — writes only from opted-in directories
# =============================================================================

# Legacy location; new resolver is paths.opt_in_paths_file() (with fallback here).
OPT_IN_PATHS_FILE = Path.home() / ".mi" / "opt-in-paths"


def load_opt_in_paths(path: Path | None = None) -> list[str]:
    """Load the capture opt-in allowlist.

    File: ``~/.memoryintelligence/mcp/opt-in-paths`` (new) with a one-release
    fallback to the legacy ``~/.mi/opt-in-paths``. One path per line; `~` is
    expanded; fnmatch globs (``*``, ``?``, ``[]``) are supported; blank lines and
    lines starting with ``#`` are ignored. Absent file → empty list → every
    capture is skipped (explicit opt-in required; matches the ownership stance).
    """
    path = path or paths.opt_in_paths_file()
    if not path.exists():
        return []
    out: list[str] = []
    for raw in path.read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        out.append(os.path.expanduser(s))
    return out


def is_cwd_opted_in(cwd: str | None = None, patterns: list[str] | None = None) -> bool:
    """Return True if ``cwd`` is covered by the opt-in allowlist.

    - ``MI_MCP_OPT_IN_ALL=1`` bypasses the check (returns True). Intended for
      testing; the server logs a warning at startup when it is set.
    - A non-glob entry matches its own directory and any subdirectory of it.
    - A glob entry (``*``/``?``/``[]``) is matched with ``fnmatch``.
    """
    if os.environ.get("MI_MCP_OPT_IN_ALL") == "1":
        return True
    # realpath (not abspath) resolves symlinks before matching — prevents a symlinked
    # cwd from bypassing or spoofing the allowlist (path-traversal class, CVE-2025-53110).
    cwd_abs = os.path.realpath(cwd if cwd is not None else os.getcwd())
    for p in (patterns if patterns is not None else load_opt_in_paths()):
        if any(c in p for c in "*?["):
            if fnmatch.fnmatch(cwd_abs, p) or fnmatch.fnmatch(cwd_abs, os.path.join(p, "*")):
                return True
        else:
            base = os.path.realpath(os.path.expanduser(p))
            if cwd_abs == base or cwd_abs.startswith(base + os.sep):
                return True
    return False
