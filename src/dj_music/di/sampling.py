"""Sampling bootstrap helpers."""

from __future__ import annotations

import logging
from typing import Any

from dj_music.core.config import settings


def build_sampling_handler(
    logger: logging.Logger | None = None,
) -> tuple[Any | None, str | None]:
    """Build the optional fallback sampling handler."""
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
            log.warning("DJ_ANTHROPIC_API_KEY set but anthropic package not installed")
    else:
        log.info(
            "No DJ_ANTHROPIC_API_KEY configured. "
            "LLM-assisted tools use client-driven mode: Claude Code generates queries "
            "and passes them via tool parameters (e.g. search_queries=[...]). "
            "For server-side sampling, set DJ_ANTHROPIC_API_KEY."
        )

    return sampling_handler, ("fallback" if sampling_handler else None)
