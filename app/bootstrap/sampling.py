"""Sampling bootstrap helpers.

Official behaviour: https://gofastmcp.com/servers/sampling
Default route is the **client** LLM; ``AnthropicSamplingHandler`` is optional
**fallback** when the client does not implement MCP sampling.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.core.constants import MCP_SAMPLING_API_KEY_ENV_NAME


def build_sampling_handler(
    logger: logging.Logger | None = None,
) -> Any | None:
    """Return ``AnthropicSamplingHandler`` when API key is set, else ``None``.

    ``server_builder`` passes ``sampling_handler_behavior="fallback"`` so the handler
    runs only when the MCP client does not support sampling (FastMCP default).
    """
    log = logger or logging.getLogger(__name__)
    sampling_handler: Any | None = None

    if settings.anthropic_api_key:
        try:
            from anthropic import AsyncAnthropic
            from fastmcp.client.sampling.handlers.anthropic import (
                AnthropicSamplingHandler,
            )

            sampling_handler = AnthropicSamplingHandler(
                default_model=settings.sampling_model,
                client=AsyncAnthropic(api_key=settings.anthropic_api_key),
            )
            log.info(
                "Sampling handler configured (Anthropic fallback, model=%s)",
                settings.sampling_model,
            )
        except ImportError:
            log.warning(
                "%s set but anthropic package not installed",
                MCP_SAMPLING_API_KEY_ENV_NAME,
            )
    else:
        log.info(
            "Sampling default: MCP client LLM (ctx.sample) — no %s required. "
            "Optional server-side Anthropic fallback: set %s and ``uv sync --extra llm``.",
            MCP_SAMPLING_API_KEY_ENV_NAME,
            MCP_SAMPLING_API_KEY_ENV_NAME,
        )

    return sampling_handler
