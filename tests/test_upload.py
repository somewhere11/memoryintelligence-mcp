"""Upload path behavior (#1166).

`mi_upload` posts multipart to /v1/upload, which runs the FULL extraction
pipeline synchronously server-side. On a slow file the client's read timeout can
fire AFTER the server has already committed the UMOs — the client raised a raw
`httpx.ReadTimeout` (empty str()) that surfaced as a blank "Unexpected error: ".
These tests pin the fix:

- upload gets an explicit, generous timeout (not the shared 30s read budget);
- a read timeout becomes an honest, non-blank MIUploadTimeout that tells the
  agent to check mi_list before retrying (writes are never auto-retried);
- the file is read via read_bytes() so no descriptor is leaked;
- the module-level unexpected-error formatter is never blank.
"""

from __future__ import annotations

import httpx
import pytest

from mi_mcp.client import MIAPIError, MIClient, MIUploadTimeout
from mi_mcp.config import MIConfig
from mi_mcp.server import _unexpected_error_text


def _client_with_scripted_post(behavior):
    """An MIClient whose underlying http.post returns/raises `behavior`, and
    records the kwargs it was called with (so we can assert timeout + files)."""
    client = MIClient(MIConfig(api_key="test-key"))
    recorded = {}

    async def fake_post(path, *, files=None, data=None, timeout=None):
        recorded["path"] = path
        recorded["files"] = files
        recorded["data"] = data
        recorded["timeout"] = timeout
        if isinstance(behavior, Exception):
            raise behavior
        return behavior

    client._http.post = fake_post  # type: ignore[method-assign]
    return client, recorded


def _write(tmp_path, name="note.txt", content=b"hello world"):
    p = tmp_path / name
    p.write_bytes(content)
    return p


@pytest.mark.asyncio
async def test_upload_read_timeout_becomes_honest_message(tmp_path):
    p = _write(tmp_path)
    client, _ = _client_with_scripted_post(httpx.ReadTimeout("slow"))
    with pytest.raises(MIUploadTimeout) as exc:
        await client.upload(str(p))
    msg = str(exc.value)
    assert msg, "the message must never be blank (that was the bug)"
    assert "mi_list" in msg, "must tell the agent how to check before retrying"


@pytest.mark.asyncio
async def test_upload_does_not_auto_retry_the_timeout(tmp_path):
    # A write that may have committed server-side must not be re-sent.
    p = _write(tmp_path)
    calls = {"n": 0}
    client = MIClient(MIConfig(api_key="test-key"))

    async def counting_post(path, *, files=None, data=None, timeout=None):
        calls["n"] += 1
        raise httpx.ReadTimeout("slow")

    client._http.post = counting_post  # type: ignore[method-assign]
    with pytest.raises(MIUploadTimeout):
        await client.upload(str(p))
    assert calls["n"] == 1, "upload writes must not be retried (double-write risk)"


@pytest.mark.asyncio
async def test_upload_uses_explicit_long_timeout_not_the_default(tmp_path):
    p = _write(tmp_path)
    client, recorded = _client_with_scripted_post(
        httpx.Response(200, json={"status": "success", "data": {}})
    )
    await client.upload(str(p))
    timeout_val = recorded["timeout"]
    assert timeout_val is not None, "upload must pass an explicit per-request timeout"
    # httpx.Timeout stores the read budget; it must be the generous upload value.
    assert timeout_val.read == MIClient._UPLOAD_TIMEOUT
    assert MIClient._UPLOAD_TIMEOUT > 30.0, "must exceed the shared 30s read default"


@pytest.mark.asyncio
async def test_upload_sends_file_bytes_and_leaks_no_handle(tmp_path):
    # read_bytes() (not an unclosed open()) — the files payload is raw bytes.
    p = _write(tmp_path, content=b"the tangerine ledger")
    client, recorded = _client_with_scripted_post(
        httpx.Response(200, json={"status": "success", "data": {"umo_id": "x"}})
    )
    result = await client.upload(str(p))
    assert result["status"] == "success"
    name, payload = recorded["files"]["file"]
    assert name == "note.txt"
    assert payload == b"the tangerine ledger"
    assert isinstance(payload, (bytes, bytearray)), "must be bytes, not an open handle"


@pytest.mark.asyncio
async def test_upload_missing_file_still_raises_file_not_found(tmp_path):
    client, _ = _client_with_scripted_post(httpx.Response(200, json={}))
    with pytest.raises(FileNotFoundError):
        await client.upload(str(tmp_path / "does-not-exist.txt"))


@pytest.mark.asyncio
async def test_upload_http_error_still_maps_to_api_error(tmp_path):
    p = _write(tmp_path)
    client, _ = _client_with_scripted_post(
        httpx.Response(413, json={"detail": "file too large"})
    )
    with pytest.raises(MIAPIError) as exc:
        await client.upload(str(p))
    assert exc.value.status_code == 413


def test_unexpected_error_text_is_never_blank_even_for_empty_str_exceptions():
    # str(httpx.ReadTimeout()) is empty — the root cause of "Unexpected error: ".
    out = _unexpected_error_text(httpx.ReadTimeout(""))
    text = out[0].text
    assert text.strip() != "Unexpected error:"
    assert "ReadTimeout" in text, "the exception type must always be visible"
