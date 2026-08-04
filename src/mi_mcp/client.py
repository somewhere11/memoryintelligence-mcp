"""Async HTTP client for the MemoryIntelligence API.

Thin wrapper around httpx that handles auth headers, error mapping,
and provides typed methods matching the canonical SDK surface.
No encryption — the MCP server is a trusted first-party client
that sends plaintext over HTTPS directly to the API.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from . import __version__
from .config import MIConfig

logger = logging.getLogger("mi_mcp.client")

# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class MIAPIError(Exception):
    """Raised when the MI API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str, endpoint: str):
        self.status_code = status_code
        self.detail = detail
        self.endpoint = endpoint
        super().__init__(f"MI API {status_code} on {endpoint}: {detail}")


class MIUploadTimeout(Exception):
    """The client's read timeout fired on /v1/upload before the response arrived.

    Distinct from a failure: /v1/upload runs the full extraction pipeline
    synchronously server-side, so a slow file can commit its UMOs AFTER the
    client gives up waiting. Writes are never auto-retried (double-write
    doctrine), so this carries an honest, actionable message for the agent
    rather than the empty ``str(httpx.ReadTimeout())`` that surfaced as a blank
    "Unexpected error:" (#1166).
    """


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class MIClient:
    """Async client for the MemoryIntelligence HTTP API.

    Designed for use inside the MCP server — one instance per server
    lifetime, reuses a single httpx.AsyncClient connection pool.
    """

    def __init__(self, config: MIConfig):
        self._config = config
        # NOTE: do NOT set Content-Type as a default header — httpx auto-sets
        # the right one per request (application/json for json=, multipart for
        # files=, etc.). Setting it here breaks the /v1/upload multipart call
        # because the leaked Content-Type confuses FastAPI's body parser.
        # See bug #261.
        self._http = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "User-Agent": f"mi-mcp-server/{__version__}",
                # X-MI-Source marks this as an LLM/agent surface. The API ALWAYS
                # redacts hard PII for agent surfaces — including the owner's own MCP —
                # because an LLM must never receive unredacted memories. This is by
                # design, not a limitation: the owner views raw values in the human dev
                # portal, never through a model context. Do not change this to an
                # owner-raw value. It mirrors the server-side agent-surface redaction policy.
                "X-MI-Source": "mcp",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            # Connection-level retries are SAFE for every verb — httpx only retries
            # when the connection never established (ConnectError/ConnectTimeout from
            # the hosted API's cold-start), so no request body is ever re-sent.
            # Read-timeout / 5xx retries are handled per-request in _request(), gated
            # on idempotency, because re-sending a write after the body landed could
            # double-apply it.
            transport=httpx.AsyncHTTPTransport(retries=2),
        )

    async def close(self):
        await self._http.aclose()

    def set_client_identity(self, name: str) -> None:
        """Forward the MCP host identity as the X-MI-Client header (#600).

        `name` is the initialize handshake's clientInfo.name (e.g.
        "claude-code"). The API uses it to resolve the provenance channel's
        platform slot — agent:claude-code instead of the transport-generic
        agent:mcp. Normalized to a registry-comparable key; empty names are
        a no-op, and unregistered ones fall back to agent:mcp server-side.
        """
        normalized = re.sub(r"[^a-z0-9._-]+", "-", (name or "").strip().lower()).strip("-")[:40]
        if normalized:
            self._http.headers["X-MI-Client"] = normalized

    # ----- helpers -----

    # Transient HTTP statuses worth a retry on idempotent reads — gateway/
    # unavailable/timeout from a saturated or cold-starting single instance.
    _RETRYABLE_STATUS = frozenset({502, 503, 504})
    # Idempotent reads get up to this many TOTAL attempts (1 initial + retries).
    _IDEMPOTENT_ATTEMPTS = 3
    _RETRY_BASE_DELAY = 0.5  # seconds; exponential: 0.5s, then 1.0s
    # /v1/upload runs the extraction pipeline synchronously, so it needs a far
    # longer read budget than the shared 30s default (#1166). Not infinite: past
    # this we return an honest "still processing, check mi_list" message.
    _UPLOAD_TIMEOUT = 120.0  # seconds

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        idempotent: bool = False,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make an API request and return the JSON response.

        ``headers`` are merged over the client's defaults for this one request
        (used by the workspace-routing headers — see ``_workspace_headers``).

        Idempotent reads (ask/list/explain/verify/match/account_info) are retried
        on a read timeout or a transient 5xx, with exponential backoff. The hosted
        API can intermittently cold-start or saturate
        (CPU-bound bge-small embed + pgvector rerank); the MCP previously had a hard
        30s budget with NO retry — the "MCP keeps timing out" report. Writes
        (capture/upload/forget/batch) are NOT read-retried: a timeout after the body
        landed server-side could double-apply. Connection-level retries (set on the
        transport) still cover the cold-start ConnectError case for every verb.
        """
        attempts = self._IDEMPOTENT_ATTEMPTS if idempotent else 1
        for attempt in range(attempts):
            is_last = attempt + 1 >= attempts
            try:
                resp = await self._http.request(
                    method, path, json=json, params=params, headers=headers
                )
            except httpx.TimeoutException:
                if is_last:
                    raise
                await asyncio.sleep(self._RETRY_BASE_DELAY * (2 ** attempt))
                continue

            if resp.status_code in self._RETRYABLE_STATUS and not is_last:
                logger.warning(
                    "MI API %s on %s %s — retrying (attempt %d/%d)",
                    resp.status_code, method, path, attempt + 1, attempts,
                )
                await asyncio.sleep(self._RETRY_BASE_DELAY * (2 ** attempt))
                continue

            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    detail = body.get("detail", resp.text)
                except Exception:
                    detail = resp.text
                raise MIAPIError(resp.status_code, str(detail), f"{method} {path}")
            return resp.json()

        # Unreachable: the loop returns or raises on the final attempt.
        raise RuntimeError(f"retry loop exhausted without result: {method} {path}")

    # ----- Core operations -----

    @staticmethod
    def _workspace_headers(workspace_id: str | None) -> dict[str, str] | None:
        """Headers that route a request to a specific workspace (#385 UC1).

        BOTH names are sent on purpose — the API has two headers for this one
        concept, and which one is honored depends on the auth plane:

        * ``X-MI-Workspace``  — the API-KEY plane (``deps.py::get_api_key``, #736).
          This is the one that matters for this package, which always authenticates
          with an ``mi_sk_*`` / ``mi_beta_*`` key.
        * ``X-Workspace-Id``  — the JWT plane (``deps.py::get_api_key_or_jwt``),
          which is what the REMOTE MCP surface (``api/public/mcp_resource.py``)
          sends. ``get_api_key_or_jwt`` forwards only ``X-MI-Workspace`` down to
          ``get_api_key``, so a key-authenticated ``X-Workspace-Id`` is IGNORED.

        Sending both means routing is correct on either plane instead of silently
        no-op'ing if this client is ever pointed at a JWT-authenticated deployment.
        The unhonored name is inert, and both planes fail CLOSED (403) on a
        workspace the caller is not a member of — enforcement stays server-side.
        """
        if not workspace_id:
            return None
        return {"X-MI-Workspace": workspace_id, "X-Workspace-Id": workspace_id}

    async def capture(
        self,
        content: str,
        *,
        source: str | None = None,
        scope: str | None = None,
        scope_id: str | None = None,
        workspace_id: str | None = None,
        retention_policy: str | None = None,
        pii_handling: str | None = None,
        metadata: dict | None = None,
        claim_granular: bool = True,
        claim_level: str | None = None,
    ) -> dict[str, Any]:
        """POST /v1/process — capture content into a UMO.

        claim_granular defaults True (#446, Decision B — atom = the CLAIM): a long
        capture persists as a parent + one child per claim, each independently
        recallable. Short single-claim captures stay a single UMO (the server's
        <=1-claim guard), so this is safe to leave on by default.

        ``workspace_id`` (#385 UC1) routes the capture to a specific workspace via
        the routing headers. Omit it and the capture goes to the caller's HOME
        workspace (the server's agent-source home-binding), which is personal for
        most users. The server validates membership and 403s a workspace the caller
        does not belong to — this client cannot route anywhere it shouldn't.
        ``scope``/``scope_id`` are a DIFFERENT axis (governance scope in the request
        body); they do not route between workspaces.
        """
        payload: dict[str, Any] = {
            "content": content,
            "source": source or self._config.default_source,
            "scope": scope or self._config.default_scope,
            "claim_granular": claim_granular,
        }
        if claim_level:
            payload["claim_level"] = claim_level
        if scope_id:
            payload["scope_id"] = scope_id
        if retention_policy:
            payload["retention_policy"] = retention_policy
        else:
            payload["retention_policy"] = self._config.default_retention
        if pii_handling:
            payload["pii_handling"] = pii_handling
        else:
            payload["pii_handling"] = self._config.default_pii_handling
        if metadata:
            payload["metadata"] = metadata

        return await self._request(
            "POST", "/v1/process", json=payload,
            headers=self._workspace_headers(workspace_id),
        )

    async def ask(
        self,
        query: str,
        *,
        scope: str | None = None,
        scope_id: str | None = None,
        workspace_id: str | None = None,
        limit: int = 10,
        offset: int = 0,
        explain: str | bool = "none",
        date_from: str | None = None,
        date_to: str | None = None,
        topics: list[str] | None = None,
        entities: list[str] | None = None,
    ) -> dict[str, Any]:
        """POST /v1/memories/query — semantic search across memories.

        ``workspace_id`` (#385 UC2) targets a workspace you are a member of; omit
        for personal (owner-scoped) search. Same routing headers as capture. Note
        the server only *widens* the read to every member's memories when its
        workspace read-isolation flag is on — see ``health()``.
        """
        payload: dict[str, Any] = {
            "query": query,
            "scope": scope or self._config.default_scope,
            "limit": limit,
            "offset": offset,
        }
        # `explain` is an API enum ("none"|"human"|"audit"|"full"), NOT a boolean.
        # Coerce legacy bool callers (True→"full", False→"none") and omit the no-op
        # "none" so we never send an illegal boolean that the API rejects with 422.
        explain_level = (
            ("full" if explain else "none") if isinstance(explain, bool) else explain
        )
        if explain_level and explain_level != "none":
            payload["explain"] = explain_level
        if scope_id:
            payload["scope_id"] = scope_id
        if date_from:
            payload["date_from"] = date_from
        if date_to:
            payload["date_to"] = date_to
        if topics:
            payload["topics"] = topics
        if entities:
            payload["entities"] = entities

        return await self._request(
            "POST", "/v1/memories/query", json=payload, idempotent=True,
            headers=self._workspace_headers(workspace_id),
        )

    async def list_memories(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        scope: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """GET /v1/memories — list UMOs with pagination.

        ``workspace_id`` (#385 UC2) targets a workspace you are a member of; omit
        for personal. See :meth:`ask` for the read-isolation caveat.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if scope:
            params["scope"] = scope
        return await self._request(
            "GET", "/v1/memories", params=params, idempotent=True,
            headers=self._workspace_headers(workspace_id),
        )

    async def health(self) -> dict[str, Any]:
        """GET /health — server status + capability discovery.

        Used for one thing here: reading
        ``capabilities.workspace_read_isolation.enabled``, which decides whether a
        workspace-targeted READ actually returns every member's memories or only
        the caller's own. Without it a workspace read looks successful and
        identical to a personal one, and any "searched the team workspace" claim
        would be unverifiable. Unauthenticated on the server side; we send the
        client's normal headers anyway (harmless).
        """
        return await self._request("GET", "/health", idempotent=True)

    async def explain(self, umo_id: str, *, level: str = "full") -> dict[str, Any]:
        """GET /v1/memories/{id}/explain — UMO introspection."""
        return await self._request(
            "GET", f"/v1/memories/{umo_id}/explain", params={"level": level}, idempotent=True
        )

    async def verify(self, umo_id: str) -> dict[str, Any]:
        """GET /v1/memories/{id}/proof — provenance verification."""
        return await self._request("GET", f"/v1/memories/{umo_id}/proof", idempotent=True)

    async def forget(self, umo_id: str) -> dict[str, Any]:
        """DELETE /v1/memories/{id} — delete a UMO with receipt."""
        return await self._request("DELETE", f"/v1/memories/{umo_id}")

    async def match(
        self,
        source_id: str,
        candidate_id: str,
        *,
        explain: str = "none",
        threshold: float = 0.7,
    ) -> dict[str, Any]:
        """POST /v1/umo/match — compare two UMOs for relevance.

        `explain` is an enum string, not a boolean. Valid values:
        'none', 'human', 'audit', 'full'. See bug #260.
        """
        return await self._request(
            "POST",
            "/v1/umo/match",
            json={
                "source_ulid": source_id,
                "candidate_ulid": candidate_id,
                "explain": explain,
                "threshold": threshold,
            },
            idempotent=True,
        )

    async def batch(
        self,
        items: list[dict[str, Any]],
        *,
        scope: str | None = None,
    ) -> dict[str, Any]:
        """POST /v1/batch — batch capture multiple items."""
        return await self._request(
            "POST",
            "/v1/batch",
            json={
                "items": items,
                "scope": scope or self._config.default_scope,
            },
        )

    async def upload(
        self,
        file_path: str,
        *,
        scope: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """POST /v1/upload — upload a media file for capture.

        Note: This uses multipart form upload, not JSON.
        """
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        data: dict[str, str] = {"scope": scope or self._config.default_scope}
        if metadata:
            import json
            data["metadata"] = json.dumps(metadata)

        # Read the bytes up front so the descriptor is closed before the await.
        # The previous `open(path, "rb")` lived in the files= dict and was never
        # closed — a leaked file handle on every upload (#1166).
        files = {"file": (path.name, path.read_bytes())}

        # Build multipart — can't use self._request helper here, so upload gets
        # none of _request's timeout handling. Give it an explicit, generous read
        # budget (the pipeline is synchronous) and translate a read timeout into
        # an HONEST message: the write may have committed after we gave up, and
        # writes are never auto-retried (double-write doctrine, see _request).
        try:
            resp = await self._http.post(
                "/v1/upload", files=files, data=data,
                timeout=httpx.Timeout(self._UPLOAD_TIMEOUT, connect=10.0),
            )
        except httpx.TimeoutException as e:
            raise MIUploadTimeout(
                "Upload timed out waiting for the server, but the file may have "
                "finished processing after the client gave up. Check `mi_list` "
                "before retrying — a retry may create a duplicate."
            ) from e
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise MIAPIError(resp.status_code, str(detail), "POST /v1/upload")
        return resp.json()

    async def account_info(self) -> dict[str, Any]:
        """GET /v1/accounts/me — get current account info and key status."""
        return await self._request("GET", "/v1/accounts/me", idempotent=True)

    async def workspaces(self) -> dict[str, Any]:
        """GET /v1/workspaces — list the caller's workspaces (mi_workspaces, #1320).

        Returns ``{"workspaces": [...], "count": N}`` where each entry carries
        id, name, the caller's role, and member_count — the routing directory
        for workspace-targeted captures. Same endpoint the remote MCP surface's
        mi_workspaces calls, so both surfaces answer identically.
        """
        return await self._request("GET", "/v1/workspaces", idempotent=True)
