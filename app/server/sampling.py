"""Server-side fallback sampling handler (Anthropic).

When ``DJ_ANTHROPIC_API_KEY`` is set, tools that call ``ctx.sample(...)``
without a client-provided LLM transport use this handler to proxy directly
to Claude. Without the key the function returns ``None`` — FastMCP with
``sampling_handler_behavior="fallback"`` then raises if the client does not
provide sampling.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

try:  # pragma: no cover - optional extra
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover
    AsyncAnthropic = None

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

SamplingHandler = Callable[..., Awaitable[Any]]


def build_sampling_handler() -> SamplingHandler | None:
    """Return an async sampling handler or ``None`` if disabled.

    Disabled when ``DJ_ANTHROPIC_API_KEY`` is unset or the ``anthropic``
    SDK is not installed.
    """
    api_key = os.getenv("DJ_ANTHROPIC_API_KEY")
    if not api_key or AsyncAnthropic is None:
        if not api_key:
            log.debug("DJ_ANTHROPIC_API_KEY unset — sampling fallback disabled")
        else:  # pragma: no cover
            log.warning("anthropic SDK unavailable — sampling fallback disabled")
        return None

    client = AsyncAnthropic(api_key=api_key)

    async def handler(messages: Any, params: Any, context: Any) -> Any:
        anthropic_messages = [
            {
                "role": "user",
                "content": getattr(m.content, "text", str(m.content)),
            }
            for m in messages
        ]
        response = await client.messages.create(
            model=_DEFAULT_MODEL,
            system=getattr(params, "system_prompt", "") or "",
            max_tokens=getattr(params, "max_tokens", 1024),
            temperature=getattr(params, "temperature", 0.2),
            messages=anthropic_messages,
        )
        # Bump LLM token counter on state if present.
        fmctx = getattr(context, "fastmcp_context", None) if context else None
        state = getattr(fmctx, "state", None) if fmctx else None
        if isinstance(state, dict):
            cost = state.setdefault("cost", {"provider_calls": 0, "llm_tokens": 0})
            usage = getattr(response, "usage", None)
            if usage is not None:
                cost["llm_tokens"] += int(
                    getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)
                )

        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        return text

    return handler
