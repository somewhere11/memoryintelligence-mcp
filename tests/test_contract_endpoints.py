"""Contract test: every endpoint the MCP server calls MUST exist in the canonical API contract.

Complements test_api_contract.py (which pins enum/param *values*). This pins *paths + methods*
against `api/contract/openapi.json` — the artifact generated from `app.openapi()` (see
scripts/gen_contract.py + docs/architecture/SYSTEM_CONTRACT.md). Because it reads the generated
contract rather than a hand-mirrored copy, it can't itself drift: if the API renames/removes a
path the MCP depends on, this fails in CI on `main` instead of in a user's chat.

Path params are matched structurally ({id} == {umo_id}), so a param rename is not a false alarm —
only a real path/method change is. Keep MCP_ENDPOINTS in sync with mi_mcp/client.py.
"""
import json
import re
from pathlib import Path

import pytest

CONTRACT = Path(__file__).resolve().parents[2] / "api" / "contract" / "openapi.json"

# (HTTP method, path) for every endpoint the MCP tools call.
MCP_ENDPOINTS = [
    ("post", "/v1/process"),                 # mi_capture
    ("post", "/v1/memories/query"),          # mi_ask
    ("get", "/v1/memories"),                 # mi_list
    ("get", "/v1/memories/{id}/explain"),    # mi_explain
    ("get", "/v1/memories/{id}/proof"),      # mi_verify
    ("delete", "/v1/memories/{id}"),         # mi_forget
    ("post", "/v1/batch"),                   # mi_batch
    ("post", "/v1/upload"),                  # mi_upload
    ("post", "/v1/umo/match"),               # mi_match
    ("get", "/v1/accounts/me"),              # mi_account
]

_HTTP = {"get", "post", "put", "patch", "delete"}


def _norm(path: str) -> str:
    """Normalize a path template so {id} and {umo_id} compare equal."""
    return re.sub(r"\{[^}]+\}", "{}", path)


@pytest.fixture(scope="module")
def spec_index():
    # The canonical contract lives in the monorepo (api/contract/). The PUBLIC
    # mirror is a subtree of mcp-server/ only, so the file is absent there — skip
    # rather than error, keeping the mirror's release CI green. In the monorepo
    # the contract exists and the test runs for real.
    if not CONTRACT.exists():
        pytest.skip(
            f"canonical API contract not present at {CONTRACT} — monorepo-only test "
            "(the public mirror is subtree-only, no api/contract/). In the monorepo, "
            "regenerate with: python scripts/gen_contract.py"
        )
    spec = json.loads(CONTRACT.read_text())
    index: dict[str, set[str]] = {}
    for path, item in spec.get("paths", {}).items():
        index.setdefault(_norm(path), set()).update(k.lower() for k in item if k.lower() in _HTTP)
    return index


@pytest.mark.parametrize("method,path", MCP_ENDPOINTS)
def test_mcp_endpoint_exists_in_contract(spec_index, method, path):
    norm = _norm(path)
    assert norm in spec_index, (
        f"MCP calls {method.upper()} {path}, but no such path is in the API contract. "
        f"Either the API removed/renamed it, or the contract is stale (run scripts/gen_contract.py)."
    )
    assert method in spec_index[norm], (
        f"MCP calls {method.upper()} {path}, but the contract only defines "
        f"{sorted(spec_index[norm])} for that path."
    )
