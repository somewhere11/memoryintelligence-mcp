"""MI MCP Server — MemoryIntelligence tools for Claude.

DEPRECATED — 0.2.14 is the FINAL release of this package (`mi-local`).
See :data:`DEPRECATION_NOTICE` and somewhere11/MemoryIntelligence#2186.
"""

import sys

__version__ = "0.2.14"

#: One line, shown on every server start and on `mi-mcp setup` / `mi-mcp doctor`.
#: Goes to STDERR only: the server speaks MCP over stdout, and one stray byte
#: there breaks the host's JSON-RPC framing. [KASEY-STATED 2026-10-19] this is
#: the last release; the desktop app carries the local MCP from here on.
DEPRECATION_NOTICE = (
    "mi-mcp (mi-local) is DEPRECATED and 0.2.14 is its final release. It keeps "
    "working, but receives no further updates. Use the MemoryIntelligence desktop "
    "app's built-in MCP (Connect Claude) on your computer, or the claude.ai "
    "MemoryIntelligence connector on the web and phone. "
    "Details: https://github.com/somewhere11/MemoryIntelligence/issues/2186"
)


def warn_deprecated(stream=None) -> None:
    """Write :data:`DEPRECATION_NOTICE` to ``stream`` (default: stderr).

    Written directly rather than through ``logging`` so it appears even when the
    host runs the server with logging quietened, and never on stdout.
    """
    out = stream if stream is not None else sys.stderr
    out.write(f"[mi-mcp] DEPRECATED: {DEPRECATION_NOTICE}\n")
    out.flush()
