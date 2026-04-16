"""Declarative set draft tools.

Session-scoped draft workflow:
  update_set_draft → preview_draft → commit_draft
  clear_draft resets at any point.

Session state key: "set_draft"
  {"name": str, "template": str|None, "track_ids": list[int]}
"""

from __future__ import annotations

import contextlib
from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.server.elicitation import CancelledElicitation, DeclinedElicitation
from fastmcp.tools import tool
from mcp.shared.exceptions import McpError
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session, get_set_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_SETS,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
)
from app.core.errors import ValidationError
from app.db.repositories.feature import FeatureRepository
from app.optimization.preview import PreviewResult, preview_arc
from app.services.set.facade import SetService
from app.templates.registry import get_template
from app.transition.scorer import TransitionScorer

_DRAFT_KEY = "set_draft"
_NO_DRAFT_MESSAGE = (
    "No draft set in this MCP session. Call update_set_draft first, then run "
    "preview_draft/commit_draft in the same active client session."
)


@tool(
    title="Update Set Draft",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def update_set_draft(
    track_ids: Annotated[
        list[int],
        Field(description="Ordered list of track IDs. Replaces the entire draft."),
    ],
    name: Annotated[
        str | None,
        Field(description="Set name (required on first call, remembered afterwards)"),
    ] = None,
    set_name: Annotated[
        str | None,
        Field(description="Alias for name (backward-compatible)"),
    ] = None,
    template: Annotated[
        str | None,
        Field(description="Set template for arc scoring (e.g. 'roller_90')"),
    ] = None,
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Store an ordered track list as the current session draft.

    Replaces the previous draft entirely. Call repeatedly as you refine
    the order — session state persists across tool calls in this session.

    Workflow: update_set_draft → preview_draft → update_set_draft → commit_draft.
    """
    if not track_ids:
        raise ValidationError("track_ids must not be empty")

    existing: dict[str, Any] = await ctx.get_state(_DRAFT_KEY) or {}
    draft_name = name if name is not None else set_name
    draft: dict[str, Any] = {
        "name": draft_name or existing.get("name") or "Untitled Set",
        "template": template if template is not None else existing.get("template"),
        "track_ids": track_ids,
    }
    await ctx.set_state(_DRAFT_KEY, draft)
    return {
        "track_count": len(track_ids),
        "name": draft["name"],
        "template": draft["template"],
        "updated": True,
    }


@tool(
    title="Clear Set Draft",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_SETS,
    meta=TOOL_META,
)
async def clear_draft(
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Reset the current session draft. Safe to call on an empty session."""
    await ctx.delete_state(_DRAFT_KEY)
    return {"cleared": True}


@tool(
    title="Preview Draft",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def preview_draft(
    track_ids: Annotated[
        list[int] | None,
        Field(
            description=(
                "Optional ordered track IDs for stateless clients. "
                "If provided, state draft is not required."
            )
        ),
    ] = None,
    template: Annotated[
        str | None,
        Field(description="Optional template override for this preview call"),
    ] = None,
    narrative: Annotated[
        bool,
        Field(description="Generate narrative ArcCritique via LLM sampling (slower)"),
    ] = False,
    ctx: Context = CurrentContext(),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Compute arc fitness for the current session draft.

    Fast mode (narrative=False): arc math only, no LLM call.
    Full mode (narrative=True): adds ArcCritique narrative via ctx.sample().

    Workflow: update_set_draft → preview_draft (iterate) → commit_draft.
    """
    draft: dict[str, Any] | None = await ctx.get_state(_DRAFT_KEY)
    if track_ids is not None:
        if not track_ids:
            raise ValidationError("track_ids must not be empty")
        active_track_ids = track_ids
        template_name: str | None = template
    elif draft and draft.get("track_ids"):
        active_track_ids = draft["track_ids"]
        template_name = template if template is not None else draft.get("template")
    else:
        raise ValidationError(_NO_DRAFT_MESSAGE)

    await ctx.report_progress(0, 3 if narrative else 2, "Loading features")

    feature_repo = FeatureRepository(session)
    features_map = await feature_repo.get_scoring_features_batch(active_track_ids)

    await ctx.report_progress(1, 3 if narrative else 2, "Computing arc")

    template_def = None
    if template_name:
        with contextlib.suppress(KeyError):
            template_def = get_template(template_name)

    scorer = TransitionScorer()
    result: PreviewResult = preview_arc(
        scorer, features_map, active_track_ids, template=template_def
    )

    output: dict[str, Any] = {
        "score": round(result.score, 4),
        "energy_arc": [round(v, 3) for v in result.energy_arc],
        "bpm_arc": [round(v, 1) for v in result.bpm_arc],
        "weak_spots": result.weak_spots,
        "track_count": len(active_track_ids),
        "template": template_name,
    }

    if narrative:
        await ctx.report_progress(2, 3, "Generating narrative")
        output["critique"] = await _generate_narrative(ctx, result, active_track_ids)

    await ctx.report_progress(3 if narrative else 2, 3 if narrative else 2, "Done")
    return output


async def _generate_narrative(
    ctx: Context,
    result: PreviewResult,
    track_ids: list[int],
) -> dict[str, Any] | None:
    """Generate ArcCritique via ctx.sample(). Returns None on any failure."""
    from app.schemas.arc_critique import ArcCritique

    try:
        psychology_result = await ctx.read_resource("knowledge://dancefloor-psychology")
        dynamics_result = await ctx.read_resource("knowledge://set-dynamics")
        _psych_raw = psychology_result.contents[0].content if psychology_result.contents else b""
        _dyn_raw = dynamics_result.contents[0].content if dynamics_result.contents else b""
        psychology = _psych_raw.decode() if isinstance(_psych_raw, bytes) else _psych_raw
        dynamics = _dyn_raw.decode() if isinstance(_dyn_raw, bytes) else _dyn_raw
        system_prompt = (
            "You are a professional DJ analyst. Analyze the following set arc data "
            "and return a structured critique.\n\n"
            f"DANCEFLOOR PSYCHOLOGY:\n{psychology}\n\n"
            f"SET DYNAMICS THEORY:\n{dynamics}"
        )
        arc_summary = (
            f"Set: {len(track_ids)} tracks\n"
            f"BPM arc: {[round(v, 1) for v in result.bpm_arc]}\n"
            f"Energy arc (LUFS): {[round(v, 2) for v in result.energy_arc]}\n"
            f"Overall score: {result.score:.2f}\n"
            f"Weak spot positions: {result.weak_spots}\n"
            f"Arc recommendation: {result.recommendation}"
        )
        sample_result = await ctx.sample(
            messages=arc_summary,
            system_prompt=system_prompt,
            result_type=ArcCritique,
            max_tokens=400,
        )
        critique: ArcCritique = sample_result.result
        return critique.model_dump()
    except Exception:
        await ctx.warning("Narrative generation unavailable — returning arc scores only")
        return None


@tool(
    title="Commit Draft",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def commit_draft(
    track_ids: Annotated[
        list[int] | None,
        Field(
            description=(
                "Optional ordered track IDs for stateless clients. "
                "If provided, state draft is not required."
            )
        ),
    ] = None,
    set_name: Annotated[
        str | None,
        Field(description="Optional set name override for this commit"),
    ] = None,
    template: Annotated[
        str | None,
        Field(description="Optional template override for this commit"),
    ] = None,
    version_label: Annotated[
        str | None,
        Field(description="Version label, e.g. 'v2-peak-hour'"),
    ] = None,
    ctx: Context = CurrentContext(),  # noqa: B008
    svc: SetService = Depends(get_set_service),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Confirm with the user then save the current draft as a set version.

    Shows a summary (track count, arc score, weak transitions) via ctx.elicit().
    On accept: saves to DB and clears the draft.
    On decline/cancel: returns {cancelled: true}, DB unchanged.

    If the client does not support elicitation, saves directly without confirmation.
    """
    draft: dict[str, Any] | None = await ctx.get_state(_DRAFT_KEY)
    using_state_draft = track_ids is None
    if track_ids is not None:
        if not track_ids:
            raise ValidationError("track_ids must not be empty")
        active_track_ids = track_ids
        name = set_name or "Untitled Set"
        template_name: str | None = template
    elif draft and draft.get("track_ids"):
        active_track_ids = draft["track_ids"]
        name = set_name or draft.get("name") or "Untitled Set"
        template_name = template if template is not None else draft.get("template")
    else:
        raise ValidationError(_NO_DRAFT_MESSAGE)

    quality: float | None = None
    weak_count = 0
    try:
        feature_repo = FeatureRepository(session)
        features_map = await feature_repo.get_scoring_features_batch(active_track_ids)
        if features_map:
            template_def = None
            if template_name:
                with contextlib.suppress(KeyError):
                    template_def = get_template(template_name)
            arc = preview_arc(
                TransitionScorer(),
                features_map,
                active_track_ids,
                template=template_def,
            )
            quality = arc.score
            weak_count = len(arc.weak_spots)
    except Exception:
        pass

    score_str = f"{quality:.2f}" if quality is not None else "n/a"
    elicit_msg = (
        f"Save '{name}': {len(active_track_ids)} tracks, score {score_str}, "
        f"{weak_count} weak transition(s). Confirm?"
    )

    try:
        elicit_result = await ctx.elicit(elicit_msg, response_type=None)
        if isinstance(elicit_result, DeclinedElicitation | CancelledElicitation):
            return {"cancelled": True}
    except McpError:
        await ctx.info("Elicitation not supported — saving draft without confirmation.")

    dj_set, version, scored_quality = await svc.commit_version(
        name=name,
        track_ids=active_track_ids,
        template=template_name,
        version_label=version_label,
    )
    if using_state_draft:
        await ctx.delete_state(_DRAFT_KEY)

    return {
        "set_id": dj_set.id,
        "version_id": version.id,
        "version_label": version.label,
        "track_count": len(active_track_ids),
        "quality_score": round(scored_quality, 4) if scored_quality is not None else None,
    }
