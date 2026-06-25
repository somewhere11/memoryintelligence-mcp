"""Retry behavior of the MI MCP client (added 0.1.12).

The Railway `sdk-api` is a single small instance that intermittently cold-starts
or saturates; the client previously had a hard 30s budget with no retry — the
"MCP keeps timing out" report. These tests pin the contract:

- Idempotent reads (ask/list/explain/verify/match) retry on a read timeout or a
  transient 5xx (502/503/504), up to `_IDEMPOTENT_ATTEMPTS` total tries.
- Writes (capture/upload/forget/batch) are NOT read-retried — a timeout after
  the body landed could double-apply.
- A non-retryable 4xx raises immediately, even for an idempotent read.

See mi_mcp.client.MIClient._request.
"""

from __future__ import annotations

import httpx
import pytest

from mi_mcp.client import MIAPIError, MIClient
from mi_mcp.config import MIConfig


def _client_with_scripted_responses(behaviors):
    """An MIClient whose underlying http.request replays a script.

    `behaviors` is a list where each element is either an Exception to raise or
    an httpx.Response to return. Each call consumes the next element (the last
    element repeats if the client makes more calls than scripted).
    """
    client = MIClient(MIConfig(api_key="test-key"))
    calls = {"n": 0}

    async def fake_http_request(method, path, *, json=None, params=None):
        i = calls["n"]
        calls["n"] += 1
        behavior = behaviors[min(i, len(behaviors) - 1)]
        if isinstance(behavior, Exception):
            raise behavior
        return behavior

    client._http.request = fake_http_request  # type: ignore[method-assign]
    return client, calls


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Collapse the backoff sleeps so the suite stays fast."""

    async def _instant(_delay):
        return None

    monkeypatch.setattr("mi_mcp.client.asyncio.sleep", _instant)


def _ok():
    return httpx.Response(200, json={"status": "success", "data": {"results": []}})


def _busy():
    return httpx.Response(503, json={"detail": "service unavailable"})


@pytest.mark.asyncio
async def test_read_retries_on_timeout_then_succeeds():
    client, calls = _client_with_scripted_responses([httpx.ReadTimeout("slow"), _ok()])
    result = await client.ask("q")  # ask is idempotent
    assert result["status"] == "success"
    assert calls["n"] == 2, "should retry once after the timeout, then succeed"


@pytest.mark.asyncio
async def test_read_retries_on_503_then_succeeds():
    client, calls = _client_with_scripted_responses([_busy(), _busy(), _ok()])
    result = await client.list_memories()
    assert result["status"] == "success"
    assert calls["n"] == 3, "should retry through two 503s, then succeed"


@pytest.mark.asyncio
async def test_read_gives_up_after_max_attempts():
    client, calls = _client_with_scripted_responses([_busy(), _busy(), _busy(), _busy()])
    with pytest.raises(MIAPIError) as exc:
        await client.list_memories()
    assert exc.value.status_code == 503
    assert calls["n"] == MIClient._IDEMPOTENT_ATTEMPTS, "must cap retries, not loop forever"


@pytest.mark.asyncio
async def test_write_does_not_retry_on_timeout():
    client, calls = _client_with_scripted_responses([httpx.ReadTimeout("slow")])
    with pytest.raises(httpx.ReadTimeout):
        await client.capture("hello")  # capture is a write
    assert calls["n"] == 1, "writes must not be read-retried (double-apply risk)"


@pytest.mark.asyncio
async def test_write_does_not_retry_on_503():
    client, calls = _client_with_scripted_responses([_busy()])
    with pytest.raises(MIAPIError) as exc:
        await client.capture("hello")
    assert exc.value.status_code == 503
    assert calls["n"] == 1, "writes get connection-retries only, not 5xx retries"


@pytest.mark.asyncio
async def test_non_retryable_4xx_raises_immediately_on_read():
    bad = httpx.Response(422, json={"detail": "bad input"})
    client, calls = _client_with_scripted_responses([bad, bad])
    with pytest.raises(MIAPIError) as exc:
        await client.ask("q")
    assert exc.value.status_code == 422
    assert calls["n"] == 1, "a 4xx is a definite answer — never retried"
