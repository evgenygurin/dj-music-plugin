from __future__ import annotations

from typing import Any

from app.domain.render.models import RenderPlan
from app.domain.render.overrides import RenderRequestOverrides, apply_overrides
from app.domain.render.request import RenderRequest
from app.handlers._orchestrator.render_executor import RenderExecutor
from app.handlers._orchestrator.render_orchestrator import RenderOrchestrator
from app.schemas.render import RenderMixdownResult
from app.shared.errors import ValidationError


def _validate_out_name(out_name: str | None) -> None:
    if not out_name:
        return
    if "/" in out_name or "\\" in out_name or out_name in {".", ".."}:
        raise ValidationError(
            f"out_name must be a bare filename, got {out_name!r}",
            details={"out_name": out_name},
        )


class _OverrideExecutor:
    """Wraps RenderExecutor to apply DSP overrides before execution.

    Injected into RenderOrchestrator via the ``executor`` constructor kwarg.
    This is the OCP seam: zero changes to existing code.
    """

    def __init__(
        self, overrides: RenderRequestOverrides, inner: RenderExecutor | None = None
    ) -> None:
        self._overrides = overrides
        self._inner = inner or RenderExecutor()

    async def execute(self, ctx: Any, request: Any, plan: RenderPlan) -> RenderMixdownResult:
        plan = apply_overrides(plan, self._overrides)
        return await self._inner.execute(ctx, request, plan)


async def render_mixdown_extended_handler(
    *,
    ctx: Any,
    uow: Any,
    version_id: int,
    workspace: str,
    timestamp: str,
    out_name: str | None = None,
    transition_bars: int | None = None,
    body_bars: int | None = None,
    refresh_grid: bool = False,
    stem: bool = True,
    subgenre: str | None = None,
    filter_sweep: str | None = None,
    echo: str | None = None,
    crossfade_curve_out: str = "tri",
    crossfade_curve_in: str = "exp",
    reverb: str | None = None,
    reverb_mix: float = 0.25,
    hpf_cutoff_hz: float | None = None,
    per_track_eq_mid_cut_db: float | None = None,
    per_track_eq_bright_boost_db: float | None = None,
    pre_comp_threshold_db: float | None = None,
    pre_comp_ratio: float | None = None,
    pre_comp_attack_ms: float | None = None,
    pre_comp_release_ms: float | None = None,
    glue_comp_threshold_db: float | None = None,
    glue_comp_ratio: float | None = None,
    glue_comp_attack_ms: float | None = None,
    glue_comp_release_ms: float | None = None,
    master_eq_air_boost_db: float | None = None,
    master_eq_mud_cut_db: float | None = None,
    master_eq_sub_boost_db: float | None = None,
    limiter_attack_ms: float | None = None,
    limiter_release_ms: float | None = None,
    limiter_ceiling: float | None = None,
    dynaudnorm_maxgain: float | None = None,
    xsplit_low_hz: int | None = None,
    xsplit_high_hz: int | None = None,
    eq_phase_1_ratio: float | None = None,
    eq_phase_2_ratio: float | None = None,
    low_swap_beats: float | None = None,
    outro_fade_bars: int | None = None,
) -> RenderMixdownResult:
    _validate_out_name(out_name)

    request = RenderRequest(
        version_id=version_id,
        workspace=workspace,
        timestamp=timestamp,
        out_name=out_name,
        transition_bars=transition_bars,
        body_bars=body_bars,
        refresh_grid=refresh_grid,
        stem=stem,
        subgenre=subgenre,
        filter_sweep=filter_sweep,
        echo=echo,
        crossfade_curve_out=crossfade_curve_out,
        crossfade_curve_in=crossfade_curve_in,
        reverb=reverb,
        reverb_mix=reverb_mix,
    )

    overrides = RenderRequestOverrides(
        hpf_cutoff_hz=hpf_cutoff_hz,
        per_track_eq_mid_cut_db=per_track_eq_mid_cut_db,
        per_track_eq_bright_boost_db=per_track_eq_bright_boost_db,
        pre_comp_threshold_db=pre_comp_threshold_db,
        pre_comp_ratio=pre_comp_ratio,
        pre_comp_attack_ms=pre_comp_attack_ms,
        pre_comp_release_ms=pre_comp_release_ms,
        glue_comp_threshold_db=glue_comp_threshold_db,
        glue_comp_ratio=glue_comp_ratio,
        glue_comp_attack_ms=glue_comp_attack_ms,
        glue_comp_release_ms=glue_comp_release_ms,
        master_eq_air_boost_db=master_eq_air_boost_db,
        master_eq_mud_cut_db=master_eq_mud_cut_db,
        master_eq_sub_boost_db=master_eq_sub_boost_db,
        limiter_attack_ms=limiter_attack_ms,
        limiter_release_ms=limiter_release_ms,
        limiter_ceiling=limiter_ceiling,
        dynaudnorm_maxgain=dynaudnorm_maxgain,
        xsplit_low_hz=xsplit_low_hz,
        xsplit_high_hz=xsplit_high_hz,
        eq_phase_1_ratio=eq_phase_1_ratio,
        eq_phase_2_ratio=eq_phase_2_ratio,
        low_swap_beats=low_swap_beats,
        outro_fade_bars=outro_fade_bars,
    )

    inner = RenderExecutor()
    override_executor = _OverrideExecutor(overrides, inner)
    orchestrator = RenderOrchestrator(uow, executor=override_executor)

    return await orchestrator.run(ctx, request)
