"""Local embedding provider (sentence-transformers). Lazy-loaded and fail-soft.

If the model cannot be loaded (e.g. no network on first run in a fully offline environment),
:func:`embed` returns ``None`` and the pipeline simply skips storing an embedding.
"""

from __future__ import annotations

import logging

from .config import get_settings

logger = logging.getLogger(__name__)

_model = None
_load_failed = False


def _get_model():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
    except Exception as exc:  # pragma: no cover - environment dependent
        _load_failed = True
        logger.warning("Embedding model unavailable (%s); embeddings disabled.", exc)
    return _model


def embed(text: str) -> list[float] | None:
    """Return a normalized embedding vector for ``text``, or ``None`` if unavailable."""
    model = _get_model()
    if model is None:
        return None
    # Keep input bounded; the models truncate anyway but this avoids needless work.
    vector = model.encode(text[:20000], normalize_embeddings=True)
    return [float(x) for x in vector]
