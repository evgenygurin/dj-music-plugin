"""Defaults and helpers for MCP ``ctx.sample()`` (structured LLM output).

Index: https://gofastmcp.com/llms.txt — sampling: https://gofastmcp.com/servers/sampling

Default route is the **client** LLM; optional server fallback:
:func:`app.bootstrap.sampling.build_sampling_handler` + ``DJ_ANTHROPIC_API_KEY`` +
``uv sync --extra llm``. Passes ``model_preferences`` from :class:`app.config.Settings`
per docs (hints for which model the client should use). Tunables: ``Settings``.
"""

from __future__ import annotations

from collections.abc import Sequence

from fastmcp.server.context import Context
from fastmcp.server.sampling import SamplingResult
from mcp.types import SamplingMessage
from pydantic import BaseModel

from app.config import settings
from app.core.constants import MCP_SAMPLING_API_KEY_ENV_NAME


def resolve_sampling_params(
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[int, float]:
    """Merge explicit overrides with :attr:`Settings.sampling_max_tokens` / ``temperature``."""
    mt = settings.sampling_max_tokens if max_tokens is None else max_tokens
    tp = settings.sampling_temperature if temperature is None else temperature
    return mt, tp


def format_sampling_unavailable_note(exc: BaseException, *, max_len: int = 400) -> str:
    """Compact reason for embedding in tool payloads (e.g. ``sampling_note``).

    Structured ``ctx.sample(..., result_type=...)`` uses a synthetic ``final_response``
    tool, so FastMCP requires the client to advertise **sampling.tools**. Cursor often
    does not; without ``DJ_ANTHROPIC_API_KEY`` + llm extra the server then raises
    ``ValueError`` (see ``fastmcp.server.sampling.run.determine_handler_mode``).
    """
    name = type(exc).__name__
    msg = str(exc).strip()
    out = name if not msg else f"{name}: {msg}"
    if len(out) > max_len:
        return out[: max_len - 3] + "..."
    return out


def format_sampling_failure_message(exc: BaseException) -> str:
    """User-facing message when ``ctx.sample`` fails.

    Default expectation: client-driven sampling (no server API key). Mention server
    fallback only as an option for environments without a capable MCP client.
    """
    return (
        f"LLM sampling failed: {exc}. "
        "With a normal IDE client, sampling uses the client LLM (no server token). "
        f"If you need server-side fallback instead, set {MCP_SAMPLING_API_KEY_ENV_NAME} "
        "and install the llm extra (see project README / CLAUDE.md)."
    )


async def sample_structured[ResultT: BaseModel](
    ctx: Context,
    messages: str | Sequence[str | SamplingMessage],
    *,
    result_type: type[ResultT],
    system_prompt: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    model_preferences: str | list[str] | None = None,
) -> SamplingResult[ResultT]:
    """Run :meth:`Context.sample` with project defaults (``model_preferences`` from docs)."""
    mt, tp = resolve_sampling_params(max_tokens=max_tokens, temperature=temperature)
    prefs = model_preferences if model_preferences is not None else settings.sampling_model
    return await ctx.sample(
        messages,
        system_prompt=system_prompt,
        result_type=result_type,
        max_tokens=mt,
        temperature=tp,
        model_preferences=prefs,
    )
