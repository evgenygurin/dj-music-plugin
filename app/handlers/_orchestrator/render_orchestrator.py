"""Compose the render mixdown pipeline from focused collaborators."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.config import get_settings
from app.domain.render.bar_plan import BarPlanner
from app.domain.render.models import RenderMode
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest
from app.handlers._orchestrator.beatgrid_provider import BeatgridProvider
from app.handlers._orchestrator.preset_applier import SubgenrePresetApplier
from app.handlers._orchestrator.render_executor import RenderExecutor
from app.handlers._orchestrator.stem_resolver import StemResolver
from app.schemas.render import RenderMixdownResult


class RenderOrchestrator:
    def __init__(
        self,
        uow: Any,
        *,
        preset_applier: Any | None = None,
        beatgrid_provider: Any | None = None,
        stem_resolver: Any | None = None,
        planner: Any | None = None,
        executor: Any | None = None,
    ) -> None:
        self._uow = uow
        self._preset = preset_applier or SubgenrePresetApplier()
        self._beatgrid = beatgrid_provider or BeatgridProvider()
        self._stems = stem_resolver or StemResolver()
        self._planner = planner or RenderPlanner()
        self._executor = executor or RenderExecutor()

    async def run(self, ctx: Any, request: RenderRequest) -> RenderMixdownResult:
        settings = get_settings().render
        await self._preset.apply(settings, ctx, request.subgenre)
        await self._beatgrid.ensure(ctx, request, self._uow)
        inputs = await self._uow.set_versions.get_render_inputs(request.version_id)
        grid = self._beatgrid.load(request.workspace)
        bar_plan = BarPlanner(settings).compute(
            inputs,
            grid,
            transition_override=request.transition_bars,
            body_override=request.body_bars,
        )
        plan_request = request
        stem_paths = None
        if request.mode is RenderMode.STEM:
            stem_paths = await self._stems.resolve(
                ctx, self._uow, inputs, workspace=request.workspace
            )
            if stem_paths is None:
                plan_request = replace(request, stem=False)
        plan = self._planner.assemble(settings, plan_request, inputs, grid, bar_plan, stem_paths)
        return await self._executor.execute(ctx, plan_request, plan)
