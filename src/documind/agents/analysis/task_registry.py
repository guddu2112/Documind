"""Task Registry — dynamic dispatch for analysis tasks.

Provides a ``@register_task`` decorator that maps a task name (as it
appears in doc-type YAML configs) to the tool function that implements it.
The ``AnalysisExecutor`` uses ``TaskRegistry.get()`` at runtime instead
of a hardcoded dict, so new doc-type tasks can be added without touching
the executor.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {}


def register_task(name: str) -> Callable:
    """Decorator — register a function as the handler for *name*.

    Usage::

        @register_task("summarize")
        def summarize_document(...):
            ...

    The name must match the ``name`` field in a doc-type YAML
    ``analysis_tasks`` entry.
    """

    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        if name in _REGISTRY:
            logger.warning(
                "Overwriting task '%s' (was %s, now %s)",
                name,
                _REGISTRY[name].__qualname__,
                fn.__qualname__,
            )
        _REGISTRY[name] = fn
        logger.debug("Registered analysis task '%s' → %s", name, fn.__qualname__)
        return fn

    return decorator


class TaskRegistry:
    """Central look-up for registered analysis task functions."""

    @staticmethod
    def get(name: str) -> Callable[..., dict[str, Any]] | None:
        """Return the handler for *name*, or ``None`` if not registered."""
        return _REGISTRY.get(name)

    @staticmethod
    def list_tasks() -> list[str]:
        """Return all registered task names."""
        return list(_REGISTRY.keys())
