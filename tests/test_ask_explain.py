"""Regression tests for the mi_ask `explain` parameter.

Bug: the MCP tool schema exposed `explain` as a boolean, but the API
`/v1/memories/query` expects an enum string ("none"|"human"|"audit"|"full").
Sending `explain: true` returned HTTP 422
("Input should be 'none', 'human', 'audit' or 'full'").

These tests pin the client's coercion so we never send an illegal boolean,
and so the no-op "none" level is omitted from the payload entirely.
"""

from __future__ import annotations

import pytest

from mi_mcp.client import MIClient
from mi_mcp.config import MIConfig


def _client_capturing_payload():
    """An MIClient whose _request records the last JSON payload instead of
    making a network call."""
    client = MIClient(MIConfig(api_key="test-key"))
    captured: dict = {}

    async def fake_request(method, path, *, json=None, params=None, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = json
        captured["params"] = params
        return {"status": "success", "data": {"results": []}}

    client._request = fake_request  # type: ignore[method-assign]
    return client, captured


@pytest.mark.asyncio
async def test_explain_none_is_omitted():
    client, captured = _client_capturing_payload()
    await client.ask("q", explain="none")
    assert "explain" not in captured["json"], "explain='none' must not be sent"


@pytest.mark.asyncio
async def test_explain_default_is_omitted():
    client, captured = _client_capturing_payload()
    await client.ask("q")
    assert "explain" not in captured["json"], "default explain must not be sent"


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["human", "audit", "full"])
async def test_explain_enum_passthrough(level):
    client, captured = _client_capturing_payload()
    await client.ask("q", explain=level)
    assert captured["json"]["explain"] == level


@pytest.mark.asyncio
async def test_explain_true_bool_coerced_to_full():
    """Legacy/defensive: a boolean True must never reach the API as a bool;
    it is coerced to the 'full' enum the API accepts."""
    client, captured = _client_capturing_payload()
    await client.ask("q", explain=True)
    assert captured["json"]["explain"] == "full"
    assert captured["json"]["explain"] is not True


@pytest.mark.asyncio
async def test_explain_false_bool_omitted():
    client, captured = _client_capturing_payload()
    await client.ask("q", explain=False)
    assert "explain" not in captured["json"]
