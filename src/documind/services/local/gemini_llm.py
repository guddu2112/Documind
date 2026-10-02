"""Gemini LLM caller for the ``local`` backend.

Uses Google's new ``google-genai`` SDK. Returns a ``Callable[[str], str]``
with the same contract as ``make_ollama_caller`` so the rest of the
pipeline is unchanged.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 503, 500, 502, 504}
_MAX_ATTEMPTS = 5


def _status_code(exc: Exception) -> int | None:
    for attr in ("code", "status_code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    return None


def make_gemini_caller(
    api_key: str | None = None,
    model: str | None = None,
    timeout: int | None = None,
    force_json: bool = True,
) -> Callable[[str], str]:
    """Return a ``Callable[[str], str]`` backed by Google Gemini."""
    api_key = api_key or settings.gemini_api_key
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — required when LOCAL_LLM_PROVIDER='gemini'."
        )
    model_name = model or settings.gemini_model
    _ = timeout or settings.gemini_timeout_seconds  # Reserved for future per-call timeout.

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    config_kwargs: dict[str, object] = {
        "temperature": settings.llm_temperature,
        "max_output_tokens": settings.gemini_max_output_tokens,
    }
    if force_json:
        config_kwargs["response_mime_type"] = "application/json"
    generate_config = types.GenerateContentConfig(**config_kwargs)

    def call_llm(prompt: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=generate_config,
                )
                return getattr(response, "text", "") or ""
            except Exception as exc:
                last_exc = exc
                code = _status_code(exc)
                text = str(exc)
                retryable = code in _RETRYABLE_STATUS or any(
                    s in text for s in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "high demand")
                )
                if not retryable or attempt == _MAX_ATTEMPTS:
                    logger.error("Gemini request failed (attempt %d): %s", attempt, exc)
                    raise
                # Exponential backoff with jitter: 2, 4, 8, 16 seconds + up to 1s jitter.
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.warning("Gemini transient error (attempt %d, retry in %.1fs): %s", attempt, delay, exc)
                time.sleep(delay)
        assert last_exc is not None
        raise last_exc

    logger.info("Gemini caller ready (model=%s)", model_name)
    return call_llm
