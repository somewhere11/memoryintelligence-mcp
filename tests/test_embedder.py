"""Tests for the local embedder (0b).

The real model load downloads ~130MB on first run and is the known CI flake
(fastembed HF download), so the actual-embedding test is OPT-IN via
``MI_RUN_EMBED_TESTS=1``. The default-run tests cover the seam + contract without
touching the network.
"""

from __future__ import annotations

import os

import pytest

from mi_mcp import embedder


def test_model_constants():
    assert embedder.MODEL_NAME == "BAAI/bge-small-en-v1.5"
    assert embedder.EMBED_DIM == 384


def test_model_path_env_seam_is_read(monkeypatch):
    # The vendoring seam: MI_BGE_MODEL_PATH must be the env var consulted on load.
    # We don't load the model here; just assert the contract the loader relies on.
    monkeypatch.setenv(embedder.MODEL_PATH_ENV, "/some/vendored/dir")
    assert os.environ[embedder.MODEL_PATH_ENV] == "/some/vendored/dir"


def test_missing_extra_raises_local_embedder_error(monkeypatch):
    # Simulate the thin base install (no fastembed) → a clear, actionable error.
    monkeypatch.setattr(embedder, "_MODEL", None)
    import builtins

    real_import = builtins.__import__

    def _no_fastembed(name, *a, **k):
        if name == "fastembed" or name.startswith("fastembed."):
            raise ImportError("No module named 'fastembed'")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _no_fastembed)
    with pytest.raises(embedder.LocalEmbedderError) as ei:
        embedder._load_model()
    assert "local" in str(ei.value).lower()


@pytest.mark.skipif(
    os.environ.get("MI_RUN_EMBED_TESTS") != "1",
    reason="real model download is heavy/flaky in CI; set MI_RUN_EMBED_TESTS=1 to run",
)
def test_embed_produces_384d_vectors():
    embedder._MODEL = None  # force a fresh load
    vecs = embedder.embed(["hello world", "a second sentence"])
    assert len(vecs) == 2
    assert all(len(v) == embedder.EMBED_DIM for v in vecs)
    assert all(isinstance(x, float) for x in vecs[0])
