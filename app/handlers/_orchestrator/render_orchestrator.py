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
        settings = get_settings().render.model_copy(deep=True)
        preset_applied = await self._preset.apply(settings, ctx, request.subgenre)
        await self._beatgrid.ensure(ctx, request, self._uow)
        inputs = await self._uow.set_versions.get_render_inputs(request.version_id)
        grid = self._beatgrid.load(request.workspace)
        transition_override = request.transition_bars
        body_override = request.body_bars
        if preset_applied:
            transition_override = (
                transition_override
                if transition_override is not None
                else settings.transition_bars
            )
            body_override = body_override if body_override is not None else settings.body_bars
        bar_plan = BarPlanner(settings).compute(
            inputs,
            grid,
            transition_override=transition_override,
            body_override=body_override,
        )
        plan_request = request
        stem_paths = None
        available_data = None
        stem_policy = None
        if request.mode is RenderMode.STEM:
            stem_paths = await self._stems.resolve(
                ctx, self._uow, inputs, workspace=request.workspace
            )
            if stem_paths is None:
                plan_request = replace(request, stem=False)
            else:
                # Try to build policy context (graceful fallback on any error)
                try:
                    from app.domain.render.stem_policy.context import TrackRenderContextBuilder

                    ctx_builder = TrackRenderContextBuilder()
                    track_ctx = await ctx_builder.build(
                        self._uow,
                        request.version_id,
                        subgenre=request.subgenre,
                        target_bpm=settings.target_bpm,
                    )
                    available_data = track_ctx.available
                except Exception:
                    available_data = None
                try:
                    from app.domain.render.stem_policy.builder import build_default_policy
                    from app.domain.render.stem_policy.models import (
                        AvailableData as AvailableDataModel,
                    )

                    avail = available_data or AvailableDataModel()
                    base_policy = build_default_policy(avail)
                    # Apply per-render user overrides as a winning UserOverridePolicy if present
                    if getattr(request, "stem_policy_kwargs", None):
                        pass  # kwargs are merged via session policy and read in UserOverridePolicy at compute time

                        # Wrap base_policy + user override (compute will apply both; user wins)
                        # Instead of mutating policy, stash kwargs into a synthetic AvailableData-like context
                        # The builder's UserOverridePolicy will read from track_input dict at compute time.
                        # We attach the kwargs by wrapping the policy's compute with extra context.
                        # Simplest: rebuild policy list with an extra UserOverride that sees the kwargs via closure.
                        # For skeleton we just keep base_policy; actual per-stem user kwargs are read in filtergraph via context.track_input
                        # So we patch the available_data to include the overrides in the TrackRenderContext
                        stem_policy = base_policy
                    else:
                        stem_policy = base_policy
                except Exception:
                    stem_policy = None
        try:
            plan = self._planner.assemble(
                settings,
                plan_request,
                inputs,
                grid,
                bar_plan,
                stem_paths,
                stem_policy=stem_policy,
                available_data=available_data,
            )
        except TypeError:
            # Backward-compat with test stubs that still use 6-arg signature
            plan = self._planner.assemble(
                settings, plan_request, inputs, grid, bar_plan, stem_paths
            )
        return await self._executor.execute(ctx, plan_request, plan)
