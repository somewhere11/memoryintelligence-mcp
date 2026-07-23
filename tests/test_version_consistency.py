"""Version-consistency guard for the ``memoryintelligence-mcp`` package.

This test ships from the monorepo (``mcp-server/tests/``) into the public mirror
via ``seed-public-mirror.sh``, so it runs in BOTH the monorepo's mcp-server test
job and the mirror's own CI (``pytest -q``). It exists because the mirror once
shipped with ``__init__.py`` at 0.2.1 and ``server.json`` at 0.2.0 while
``pyproject.toml`` was 0.2.2: the monorepo's ``scripts/mcp/version_guard.py`` runs
upstream and is NOT shipped to the mirror, so the public package had no guard of
its own. This is that guard, living inside the package so it travels with it.

The package version is declared in three files that must always agree::

    pyproject.toml            [project].version
    src/mi_mcp/__init__.py    __version__            (a literal, by design)
    server.json               .version  AND  .packages[0].version

Layout-agnostic: ``tests/`` sits directly under the package root in both the
monorepo (``mcp-server/``) and the mirror (repo root), so ``parents[1]`` resolves
the root in either place.
"""

from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    # tomllib is stdlib only on 3.11+, but CI runs a 3.10 matrix leg — parse the
    # [project].version line directly instead of importing a TOML library.
    section = None
    for line in (ROOT / "pyproject.toml").read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
        elif section == "[project]" and stripped.startswith("version"):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise AssertionError("no [project].version found in pyproject.toml")


def _init_version() -> str:
    # A literal is required by design (the monorepo's version_guard.py parses it).
    # If __init__ ever stops declaring one, this raises and the test fails loudly.
    for line in (ROOT / "src/mi_mcp/__init__.py").read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("__version__"):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise AssertionError("no __version__ literal found in src/mi_mcp/__init__.py")


def _server_json_versions() -> tuple[str, str]:
    data = json.loads((ROOT / "server.json").read_text())
    return data["version"], data["packages"][0]["version"]


def test_version_files_agree():
    """pyproject, __init__, and both server.json fields must be identical."""
    server_top, server_pkg = _server_json_versions()
    versions = {
        "pyproject.toml [project].version": _pyproject_version(),
        "src/mi_mcp/__init__.py __version__": _init_version(),
        "server.json .version": server_top,
        "server.json .packages[0].version": server_pkg,
    }
    assert len(set(versions.values())) == 1, "mcp package version files disagree: " + ", ".join(
        f"{name}={value!r}" for name, value in versions.items()
    )


def test_module_version_matches_pyproject():
    """The imported package reports the same version the metadata declares."""
    mi_mcp = pytest.importorskip("mi_mcp")
    assert mi_mcp.__version__ == _pyproject_version()
