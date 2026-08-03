"""Server identity + tool-surface pins (#1320).

The local stdio server and the REMOTE MCP resource used to be indistinguishable
on a client hosting both (the local announced plain "memoryintelligence"; the
remote announces "memoryintelligence-remote" but is typically displayed as
"memoryintelligence") — during the 2026-08-02 debug the local's tools silently
masqueraded as the remote's. These tests pin the two properties that fix keeps:

  1. the local server announces itself as "mi-local", and
  2. mi_workspaces exists on the local surface (tool-set parity with the remote),
     in the DEFAULT surface, annotated read-only.

Network-free: constructing the server makes no API call.
"""

from __future__ import annotations

from mi_mcp.config import MIConfig
from mi_mcp.server import V0_VISIBLE_TOOLS, _TOOL_ANNOTATIONS, create_server


def test_server_announces_mi_local():
    # NOT "memoryintelligence" — that collides with the remote surface's typical
    # display name; and NOT "memoryintelligence-remote" — that's the remote itself.
    server = create_server(MIConfig(api_key="test-key"))
    assert server.name == "mi-local"


def test_mi_workspaces_in_default_surface():
    assert "mi_workspaces" in V0_VISIBLE_TOOLS
    # 7 tools visible by default (#256 narrowing + #1320 parity).
    assert len(V0_VISIBLE_TOOLS) == 7


def test_full_surface_is_eleven_tools():
    # Every tool carries an annotation, so the annotation map is the full surface.
    assert len(_TOOL_ANNOTATIONS) == 11
    assert V0_VISIBLE_TOOLS <= set(_TOOL_ANNOTATIONS)


def test_mi_workspaces_annotated_read_only():
    # Matches the remote surface's annotation for the same tool (#1321).
    ann = _TOOL_ANNOTATIONS["mi_workspaces"]
    assert ann.title == "List workspaces"
    assert ann.readOnlyHint is True
