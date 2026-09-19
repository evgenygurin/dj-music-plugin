"""Server-side fallback sampling handler via OmniRoute.

When OMNIROUTE_API_KEY is set, tools that call ctx.sample(...)
without a client-provided LLM transport use this handler to proxy through
the same OmniRoute gateway as Hermes/OpenCode.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "dj-free-fast"
_DEFAULT_BASE_URL = "https://omniroute-production-a7ce.up.railway.app/v1"

SamplingHandler = Callable[..., Awaitable[Any]]


def build_sampling_handler() -> SamplingHandler | None:
    """Return an async OmniRoute sampling handler or None if disabled."""
    api_key = os.getenv("OMNIROUTE_API_KEY")
    if not api_key:
        log.debug("OMNIROUTE_API_KEY unset - sampling fallback disabled")
        return None

    base_url = os.getenv("OMNIROUTE_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("DJ_SAMPLING_MODEL", _DEFAULT_MODEL)

    client = httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=httpx.Timeout(120.0, connect=10.0),
    )

    async def handler(messages: Any, params: Any, context: Any) -> Any:
        chat_messages: list[dict[str, str]] = []
        system_prompt = getattr(params, "system_prompt", "") or ""
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})

        for message in messages:
            content = getattr(message, "content", "")
            text = getattr(content, "text", None)
            if text is None:
                text = str(content)
            chat_messages.append({"role": "user", "content": text})

        response = await client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": chat_messages,
                "max_tokens": getattr(params, "max_tokens", 1024),
                "temperature": getattr(params, "temperature", 0.2),
            },
        )
        response.raise_for_status()
        payload = response.json()

        choice = (payload.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content") or "").strip()

        usage = payload.get("usage") or {}
        fmctx = getattr(context, "fastmcp_context", None) if context else None
        state = getattr(fmctx, "state", None) if fmctx else None
        if isinstance(state, dict):
            cost = state.setdefault("cost", {"provider_calls": 0, "llm_tokens": 0})
            cost["provider_calls"] += 1
            cost["llm_tokens"] += int(
                usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            )

        return text

    return handler
