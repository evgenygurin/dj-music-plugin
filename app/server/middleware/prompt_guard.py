"""Middleware that guards against OpenCode prompting prompts with unresolved

template variables (``$1``, ``$2``) instead of real arguments.

When OpenCode discovers a prompt, it calls ``getPrompt(name, {"arg": "$1"})``
with literal ``$N`` placeholders. FastMCP's typed parameters reject ``"$1"``
for ``int`` args (fast), but prompts with ``str`` or no args execute fully,
and with 35+ prompts the cumulative time can exceed OpenCode's readiness
timeout. This middleware returns a placeholder immediately when arguments
contain ``$N`` patterns, so every prompt resolves instantly during discovery.
"""

from __future__ import annotations

import re

import mcp.types as mt
from fastmcp.prompts import Message, PromptResult
from fastmcp.server.middleware.middleware import (
    CallNext,
    Middleware,
    MiddlewareContext,
)

_PLACEHOLDER_RE = re.compile(r"^\$\d+$")


class PromptGuardMiddleware(Middleware):
    """MCP middleware that prevents prompt-get calls with placeholder arguments

    from reaching the real prompt handler.
    """

    async def on_get_prompt(
        self,
        context: MiddlewareContext[mt.GetPromptRequestParams],
        call_next: CallNext[mt.GetPromptRequestParams, PromptResult],
    ) -> PromptResult:
        args = context.message.arguments or {}
        for key, value in args.items():
            if isinstance(value, str) and _PLACEHOLDER_RE.match(value):
                msg = f"Prompt '{context.message.name}' requires a real argument for '{key}'."
                return PromptResult(
                    messages=[Message(msg)],
                    description=f"Preview placeholder — call with real {key} value.",
                )
        return await call_next(context)
