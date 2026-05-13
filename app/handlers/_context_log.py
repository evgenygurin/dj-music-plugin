"""Safe wrappers around ``ctx.info`` / ``ctx.warning`` / ``ctx.error`` /
``ctx.report_progress``.

FastMCP's ``Context.info()`` (and siblings — ``warning``, ``error``,
``report_progress``) require an active MCP session — internally they
call ``ctx.session.send_log_message(...)`` / ``send_progress_notification(...)``.
When the same tool / handler is invoked from a unit test or any other
in-process headless caller, ``ctx.session`` raises ``RuntimeError("session
is not available because the MCP session has not been established yet")``.

Five handlers (``track_import``, ``track_features_{analyze,reanalyze}``,
``audio_file_download``, ``set_version_build``) emit a progress log via
``await ctx.info(...)`` near the end of their happy path; four of them
also stream per-item progress via ``await ctx.report_progress(...)``.
Without these wrappers a successful build silently crashed in headless
mode at the first progress event — the caller saw ``"session is not
available …"`` even though the work actually completed. The wrappers
fall back to the stdlib logger when no session exists, so handlers
stay observable in any execution mode.
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
        # No active MCP session (unit test / headless caller) — fall back
        # to process logger so the message isn't silently dropped.
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


async def safe_report_progress(
    ctx: Any,
    *,
    progress: float,
    total: float | None = None,
    message: str | None = None,
) -> None:
    """``await ctx.report_progress(...)`` if a session is live, else no-op debug.

    ``ctx.report_progress`` actually has a partial short-circuit for the
    case where there's no ``progressToken`` on the request, but it can
    still hit ``ctx.session`` later in the call path under Docket-task
    or other indirect contexts. Wrap it the same way as ``ctx.info`` so
    unit-test / headless callers can't crash mid-batch on a progress event.
    The stdlib fall-back is ``debug`` (not ``info``) because per-item
    progress is too chatty for the main log; we only want it on
    explicit DEBUG.
    """
    try:
        await ctx.report_progress(progress=progress, total=total, message=message)
    except RuntimeError:
        if message:
            log.debug("progress %s/%s: %s", progress, total, message)
        else:
            log.debug("progress %s/%s", progress, total)
