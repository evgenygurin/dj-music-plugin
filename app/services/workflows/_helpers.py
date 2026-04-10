"""Shared helpers for workflow orchestration."""

from __future__ import annotations

import inspect
from typing import Any


async def call_async_method(target: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    """Call a method when present, awaiting the result if needed."""
    if target is None:
        return None
    method = getattr(target, method_name, None)
    if method is None:
        return None
    result = method(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result
