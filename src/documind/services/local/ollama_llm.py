"""Local LLM + embedding factories.

- ``make_ollama_caller()``  → ``Callable[[str], str]`` that talks to a
  running Ollama server (`http://localhost:11434` by default).
- ``make_st_embedder()``    → ``Callable[[str], list[float]]`` that
  encodes text with a sentence-transformers model, fully offline after
  the model is cached locally.

Both callables load their heavy dependencies lazily so this module is
cheap to import.
"""

from __future__ import annotations

import logging
from typing import Callable

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)


# ── Ollama chat caller ───────────────────────────────────────────


def make_ollama_caller(
    base_url: str | None = None,
    model: str | None = None,
    timeout: int | None = None,
    force_json: bool = True,
) -> Callable[[str], str]:
    """Return a ``Callable[[str], str]`` bound to a local Ollama server."""
    base_url = (base_url or settings.ollama_base_url).rstrip("/")
    model = model or settings.ollama_model
    timeout = timeout or settings.ollama_timeout_seconds

    import httpx

    # Separate connect vs. read timeouts: the model can take a long time
    # to load on the first call (CPU inference of an 8B model), so we
    # give reads a long ceiling while keeping connect fast.
    client_timeout = httpx.Timeout(
        connect=10.0,
        read=float(timeout),
        write=float(timeout),
        pool=float(timeout),
    )
    client = httpx.Client(base_url=base_url, timeout=client_timeout)

    def call_llm(prompt: str) -> str:
        payload: dict[str, object] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": settings.llm_temperature,
                # Cap generation so a runaway response can't stall the pipeline.
                "num_predict": settings.ollama_num_predict,
                # Context window must fit the prompt or Ollama silently truncates and thrashes.
                "num_ctx": settings.ollama_num_ctx,
            },
        }
        if force_json:
            payload["format"] = "json"

        try:
            response = client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama HTTP %s: %s", exc.response.status_code, exc.response.text[:500])
            raise
        except httpx.HTTPError as exc:
            logger.error("Ollama request failed: %s", exc)
            raise

        data = response.json()
        message = data.get("message") or {}
        return message.get("content", "") or ""

    logger.info("Ollama caller ready (base_url=%s model=%s)", base_url, model)
    return call_llm


# ── Sentence-transformers embedder ───────────────────────────────

_ST_MODEL_CACHE: dict[str, object] = {}


def _get_st_model(model_id: str):
    """Load (once, cached) a sentence-transformers model."""
    cached = _ST_MODEL_CACHE.get(model_id)
    if cached is not None:
        return cached
    from sentence_transformers import SentenceTransformer

    logger.info("Loading sentence-transformers model %s …", model_id)
    model = SentenceTransformer(model_id)
    _ST_MODEL_CACHE[model_id] = model
    return model


def make_st_embedder(
    model_id: str | None = None,
) -> Callable[[str], list[float]]:
    """Return a ``Callable[[str], list[float]]`` using sentence-transformers."""
    model_id = model_id or settings.local_embedding_model

    def embed(text: str) -> list[float]:
        model = _get_st_model(model_id)
        # SentenceTransformer.encode returns numpy; convert to Python floats.
        vec = model.encode(text or " ", normalize_embeddings=True)
        return [float(x) for x in vec.tolist()]

    return embed
