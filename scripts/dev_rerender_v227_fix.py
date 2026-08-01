"""Headless re-render of set version 227 with the fixed kick-grid pipeline.

Uses the CURRENT code (not the stale MCP server): recomputes the beatgrid
(refresh_grid=True) via the new detect_kick_trim/refine_phase, then runs the
full stem render through RenderOrchestrator, reusing cached demucs stems.
"""

import asyncio
import sys

from app.db.session import get_session_factory
from app.domain.render.request import RenderRequest
from app.handlers._orchestrator.render_orchestrator import RenderOrchestrator
from app.repositories.unit_of_work import UnitOfWork


async def main() -> None:
    sf = get_session_factory()
    async with sf() as session:
        uow = UnitOfWork(session)
        request = RenderRequest(
            version_id=227,
            workspace="/Users/laptop/dev/dj-music-plugin/generated-sets/render/v227",
            timestamp="20260801-fix",
            out_name="MIX_fixed.mp3",
            refresh_grid=True,
            stem=True,
            subgenre="peak_time_techno",
        )
        res = await RenderOrchestrator(uow).run(None, request)
        print(f"RESULT {res.job_id} -> {res.out_path} dur={res.duration_s:.1f}s", flush=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
