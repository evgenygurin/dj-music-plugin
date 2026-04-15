"""Set tools: CRUD, build, rebuild, score, cheat sheet, templates (8 tools).

Thin wrappers calling :class:`SetService` / :class:`BuildSetWorkflow`
via ``Depends()``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_build_set_workflow, get_feature_repo, get_set_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_SETS,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    ensure_reference,
    map_domain_errors,
)
from app.core.utils.parsing import ensure_dict
from app.db.repositories.feature import FeatureRepository
from app.optimization.preview import PreviewResult, preview_arc
from app.services.set.facade import SetService
from app.services.workflows.build_set_workflow import BuildSetWorkflow
from app.templates.registry import TEMPLATES
from app.transition.scorer import TransitionScorer

SetManageAction = Literal[
    "create", "update", "delete", "add_constraint", "remove_constraint", "add_feedback"
]
SetView = Literal["summary", "tracks", "transitions", "full"]


# ── CRUD ─────────────────────────────────────────────────────────────


@tool(
    title="List Sets",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def list_sets(
    template: Annotated[str | None, Field(description="Filter sets by template name")] = None,
    limit: Annotated[int, Field(description="Page size", ge=1)] = 20,
    cursor: Annotated[
        str | None, Field(description="Pagination cursor from previous page")
    ] = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Lists DJ sets with optional template filter and cursor pagination. Use when browsing the set catalog or fetching the next page of results."""
    return await svc.list_sets(template=template, limit=limit, cursor=cursor)


@tool(
    title="Get Set",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def get_set(
    id: Annotated[int | None, Field(description="Local set ID")] = None,
    query: Annotated[str | None, Field(description="Text query to resolve a set")] = None,
    view: Annotated[SetView, Field(description="Detail level")] = "summary",
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Returns one DJ set by local id or text query at the requested detail level. Use when inspecting a set before editing, exporting, or comparing versions."""
    ensure_reference(id, query, entity_name="set")
    return await svc.get_set(id=id, query=query, view=view)


@tool(
    title="Manage Set",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def manage_set(
    action: Annotated[SetManageAction, Field(description="Operation to perform")],
    data: Annotated[Any, Field(description="Action-specific payload dict")] = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Applies create, update, delete, constraint, or feedback changes to a set via one action and payload. Use when mutating set metadata or structure rather than read-only inspection."""
    return await svc.manage_set(action=action, data=ensure_dict(data))


# ── Building ─────────────────────────────────────────────────────────


@tool(
    title="Build Set",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def build_set(
    name: Annotated[str, Field(description="Set name")],
    playlist_id: Annotated[int | None, Field(description="Source playlist ID")] = None,
    source: Annotated[
        Literal["playlist", "library"], Field(description="Track source")
    ] = "playlist",
    template: Annotated[str | None, Field(description="Set template name")] = None,
    target_duration_min: Annotated[
        int | None, Field(description="Target set duration in minutes")
    ] = None,
    algorithm: Annotated[
        Literal["greedy", "ga"], Field(description="Optimization algorithm")
    ] = "greedy",
    dry_run: Annotated[bool, Field(description="Preview without saving")] = False,
    bpm_min: Annotated[float | None, Field(description="Minimum BPM filter")] = None,
    bpm_max: Annotated[float | None, Field(description="Maximum BPM filter")] = None,
    moods: Annotated[list[str] | None, Field(description="Filter by subgenre moods")] = None,
    energy_min: Annotated[float | None, Field(description="Minimum energy (LUFS-related)")] = None,
    energy_max: Annotated[float | None, Field(description="Maximum energy (LUFS-related)")] = None,
    pool_size: Annotated[int, Field(description="Max candidate pool size", ge=10)] = 500,
    workflow: Annotated[
        BuildSetWorkflow,
        Field(description="Injected build-set workflow"),
    ] = Depends(get_build_set_workflow),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="Optional MCP request context"),
    ] = None,
) -> dict[str, Any]:
    """Builds an optimized DJ set from a playlist or the library with greedy or GA optimization. Use when creating or dry-running a set from a playlist or filtered pool. ``source="playlist"`` requires ``playlist_id``; ``source="library"`` uses BPM/mood/energy filters without downloading audio."""
    return await workflow.build_set(
        playlist_id=playlist_id,
        name=name,
        source=source,
        template=template,
        target_duration_min=target_duration_min,
        algorithm=algorithm,
        dry_run=dry_run,
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        moods=moods,
        energy_min=energy_min,
        energy_max=energy_max,
        pool_size=pool_size,
        log=ToolContext(ctx),
    )


@tool(
    title="Rebuild Set",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def rebuild_set(
    set_id: Annotated[int, Field(description="DJ set ID to rebuild")],
    pin_tracks: Annotated[
        list[int] | None, Field(description="Track IDs that must stay in order")
    ] = None,
    exclude_tracks: Annotated[
        list[int] | None, Field(description="Track IDs to remove from the pool")
    ] = None,
    algorithm: Annotated[
        Literal["greedy", "ga"], Field(description="Optimization algorithm")
    ] = "greedy",
    version_label: Annotated[
        str | None, Field(description="Label for the new set version")
    ] = None,
    workflow: Annotated[
        BuildSetWorkflow,
        Field(description="Injected build-set workflow"),
    ] = Depends(get_build_set_workflow),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="Optional MCP request context"),
    ] = None,
) -> dict[str, Any]:
    """Rebuilds an existing set into a new version with optional pinned or excluded tracks. Use when refining order while keeping anchors or shrinking the candidate pool."""
    return await workflow.rebuild_set(
        set_id=set_id,
        pin_tracks=pin_tracks,
        exclude_tracks=exclude_tracks,
        algorithm=algorithm,
        version_label=version_label,
        log=ToolContext(ctx),
    )


@tool(
    title="Score Transitions",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def score_transitions(
    mode: Annotated[
        Literal["set", "pair", "track_candidates"],
        Field(description="Scoring mode"),
    ] = "set",
    set_id: Annotated[int | None, Field(description="Set ID when mode is set")] = None,
    from_track_id: Annotated[
        int | None, Field(description="Outgoing track ID (pair mode)")
    ] = None,
    to_track_id: Annotated[int | None, Field(description="Incoming track ID (pair mode)")] = None,
    track_id: Annotated[
        int | None, Field(description="Anchor track ID (track_candidates mode)")
    ] = None,
    top_n: Annotated[
        int, Field(description="Max ranked transitions or candidates to persist")
    ] = 10,
    workflow: Annotated[
        BuildSetWorkflow,
        Field(description="Injected build-set workflow"),
    ] = Depends(get_build_set_workflow),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="Optional MCP request context"),
    ] = None,
) -> dict[str, Any]:
    """Scores transitions for a set, a single pair, or anchor candidates and persists results. Use when auditing blends, ranking options, or refreshing stored transition scores."""
    return await workflow.score_transitions(
        mode=mode,
        set_id=set_id,
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        track_id=track_id,
        top_n=top_n,
        log=ToolContext(ctx),
    )


@tool(
    title="Set Cheat Sheet",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def get_set_cheat_sheet(
    set_id: Annotated[int, Field(description="DJ set ID")],
    version: Annotated[str | None, Field(description="Set version label (optional)")] = None,
    svc: Annotated[
        SetService,
        Field(description="Injected set service"),
    ] = Depends(get_set_service),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="Optional MCP request context"),
    ] = None,
) -> str:
    """Returns a human-readable BPM, key, and energy-arc summary for a set version. Use when reviewing flow on paper or in the booth before playback."""
    return await svc.get_cheat_sheet(set_id, version=version)


@tool(
    title="Get Set Templates",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
async def get_set_templates() -> dict[str, Any]:
    """Lists registered DJ set templates with slot definitions (moods, BPM, energy). Use when choosing a ``template`` argument for ``build_set`` or comparing archetypes."""
    return {
        "templates": [
            {
                "name": tpl.name,
                "duration_min": tpl.duration_min,
                "description": tpl.description,
                "slots": [
                    {
                        "position": slot.position,
                        "target_mood": slot.target_mood,
                        "energy_lufs": slot.energy_lufs,
                        "bpm_min": slot.bpm_min,
                        "bpm_max": slot.bpm_max,
                        "duration_ms": slot.duration_ms,
                        "flexibility": slot.flexibility,
                    }
                    for slot in tpl.slots
                ],
            }
            for tpl in TEMPLATES.values()
        ]
    }


@tool(
    title="Preview Set Arc",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def preview_set_arc(
    track_ids: Annotated[list[int], Field(description="Ordered list of track IDs to evaluate")],
    template: Annotated[
        str | None,
        Field(
            description="Optional template name (e.g. 'roller_90') for template fitness scoring"
        ),
    ] = None,
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
) -> dict[str, Any]:
    """Evaluate a track ordering's fitness without saving a set version.

    Runs the same fitness function used by build_set, but non-destructively.
    Use before committing to an ordering — compare multiple arc shapes and
    identify weak transitions before calling build_set or rebuild_set.

    Returns score (0-1), energy/BPM arcs, weak spot positions, and a
    plain-language recommendation.
    """
    from dataclasses import asdict

    if not track_ids:
        return asdict(
            PreviewResult(
                score=1.0,
                energy_arc=[],
                bpm_arc=[],
                weak_spots=[],
                recommendation="No tracks provided.",
                missing_track_ids=[],
            )
        )

    features_map = await feat_repo.get_scoring_features_batch(track_ids)
    scorer = TransitionScorer()
    template_def = TEMPLATES.get(template) if template is not None else None

    result = preview_arc(scorer, features_map, track_ids, template=template_def)
    return asdict(result)
