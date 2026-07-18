"""Local document/query embedder — bge-small via fastembed (the ``[local]`` extra).

This is the network-free embedder that lets the vault be ranked offline. It MUST
produce the same model's vectors as capture (``BAAI/bge-small-en-v1.5``, 384-d) or
local vectors won't compare to anything. fastembed (ONNX) + onnxruntime are real
weight, so they live in the ``[local]`` extra, NOT the thin base server-client, and
are imported lazily — merely importing this module never pulls them in.

DISTRIBUTION (decided 2026-06-23): download-on-first-run by default — fastembed
fetches the ONNX model on first use and caches it (``~/.cache/fastembed`` or
``$MI_BGE_MODEL_PATH``). ``MI_BGE_MODEL_PATH`` is the drop-in seam for a *vendored*
model directory: a sealed school appliance / notarized desktop build points it at a
bundled model so the first run needs no network. Swapping to a fully-vendored wheel
later is then a packaging change, not a code change.

PARITY NOTE: queries and documents are embedded the SAME way (no asymmetric bge
retrieval prefix), because backfill embeds the documents here too — both sides share
this code, so they share a vector space. If capture-side embedding ever diverges,
reconcile here.
"""

from __future__ import annotations

import os

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

# Override the model cache / vendored-model location (the offline seam).
MODEL_PATH_ENV = "MI_BGE_MODEL_PATH"

_MODEL = None  # process-lifetime singleton — load once, reuse (warm).


class LocalEmbedderError(Exception):
    """Raised when the local embedder can't be loaded (missing extra, etc.)."""


def _load_model():
    """Load (once) and return the fastembed model. Lazy + cached."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from fastembed import TextEmbedding
    except ImportError as e:  # pragma: no cover - depends on install extras
        raise LocalEmbedderError(
            "Local embedding needs the 'local' extra (fastembed + onnxruntime).\n"
            "Install:  pip install 'memoryintelligence-mcp[local]'"
        ) from e

    kwargs: dict = {}
    model_path = os.environ.get(MODEL_PATH_ENV)
    if model_path:
        # Point fastembed at a vendored / pre-downloaded model dir → no network.
        kwargs["cache_dir"] = model_path
    try:
        _MODEL = TextEmbedding(model_name=MODEL_NAME, **kwargs)
    except Exception as e:  # network failure, bad vendored path, etc.
        raise LocalEmbedderError(
            f"could not load embedding model {MODEL_NAME!r}: {e}. "
            f"For offline use, set {MODEL_PATH_ENV} to a vendored model directory."
        ) from e
    return _MODEL


def warm() -> None:
    """Preload the model so the first real query/backfill doesn't pay the load.

    The cold-start cost of local reads is the model load + first embed, not the
    cosine search (<1ms/50k). Call this at server start to keep ``mi_ask`` fast.
    """
    _load_model()


def embed(texts) -> list[list[float]]:
    """Embed a sequence of texts → list of 384-d float vectors (batched)."""
    model = _load_model()
    return [[float(x) for x in vec] for vec in model.embed(list(texts))]


def embed_one(text: str) -> list[float]:
    """Embed a single text → one 384-d float vector."""
    return embed([text])[0]
