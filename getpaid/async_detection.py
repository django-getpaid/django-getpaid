"""Helpers for detecting async callables across wrapped processor methods."""

from __future__ import annotations

import inspect
from typing import Any


def is_async_callable(value: Any) -> bool:
    """Return True when a callable ultimately resolves to an async function."""
    target = inspect.unwrap(value)
    if inspect.iscoroutinefunction(target):
        return True

    if not callable(target):
        return False
    return inspect.iscoroutinefunction(
        inspect.unwrap(target.__call__)
    )
