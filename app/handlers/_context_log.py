"""Safe wrappers around ``ctx.info`` / ``ctx.warning`` / ``ctx.error``.

FastMCP's ``Context.info()`` (and siblings) require an active MCP session —
internally they call ``ctx.session.send_log_message(...)``. When the same
tool / handler is invoked through the REST proxy (``app/rest/``, no MCP
session), or from a unit test, ``ctx.session`` raises
``RuntimeError("session is not available because the MCP session has not
been established yet")``.

Five handlers (``track_import``, ``track_features_{analyze,reanalyze}``,
``audio_file_download``, ``set_version_build``) emit a progress log via
``await ctx.info(...)`` near the end of their happy path. Without this
wrapper, every successful build silently crashed in REST mode after the
DB writes had landed — the caller saw ``"session is not available …"``
even though the work actually completed. The wrapper falls back to
the stdlib logger when no session exists, so handlers stay observable
in stdio AND REST modes.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


async def safe_info(ctx: Any, message: str) -> None:
    """``await ctx.info(message)`` if a session is live, else log locally."""
    try:
        await ctx.info(message)
    except RuntimeError:
        # No active MCP session (REST proxy / unit test) — fall back to
        # process logger so the message isn't silently dropped.
        log.info(message)


async def safe_warning(ctx: Any, message: str) -> None:
    try:
        await ctx.warning(message)
    except RuntimeError:
        log.warning(message)


async def safe_error(ctx: Any, message: str) -> None:
    try:
        await ctx.error(message)
    except RuntimeError:
        log.error(message)
