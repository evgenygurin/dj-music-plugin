"""Set tools: CRUD, commit, score, cheat sheet, templates.

Thin wrappers calling :class:`SetService` / :class:`BuildSetWorkflow`
via ``Depends()``.
"""

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import (
    get_build_set_workflow,
    get_feature_repo,
    get_set_repo,
    get_set_service,
)
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_SETS,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ensure_reference,
    map_domain_errors,
)
from app.controllers.tools._shared.structured_multiline import split_multiline_for_json_ui
from app.core.utils.parsing import ensure_dict, ensure_list
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.optimization.preview import preview_arc
from app.schemas.tool_output import (
    GetSetCheatSheetResult,
    GetSetTemplatesResult,
    ListSetsResult,
    SearchTransitionsResult,
    SetArcPreview,
    SetTemplateEntry,
    SetTemplateSlotRow,
    SetVersionResult,
)
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
) -> ListSetsResult:
    """Lists DJ sets with optional template filter and cursor pagination. Use when browsing the set catalog or fetching the next page of results."""
    raw = await svc.list_sets(template=template, limit=limit, cursor=cursor)
    return ListSetsResult.model_validate(raw)


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
    data: Annotated[
        Any,
        Field(
            description=(
                "Action payload dict. Examples by action:\n"
                "  create: {name, template_name?}\n"
                "  update: {id, name?, template_name?}\n"
                "  delete: {id}\n"
                "  add_constraint: {id, constraint_type, value}\n"
                "  add_feedback:   {id, feedback}"
            )
        ),
    ] = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Applies create, update, delete, constraint, or feedback changes to a set via one action and payload. Use when mutating set metadata or structure rather than read-only inspection."""
    return await svc.manage_set(action=action, data=ensure_dict(data))


# ── Declarative commit ───────────────────────────────────────────────


@tool(
    title="Commit Set Version",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def commit_set_version(
    name: Annotated[str, Field(description="Set name (used when creating a new set)")],
    track_ids: Annotated[
        list[int], Field(description="Ordered list of track IDs chosen by the AI")
    ],
    set_id: Annotated[
        int | None,
        Field(description="Existing set ID to add a new version to (omit to create a new set)"),
    ] = None,
    template: Annotated[str | None, Field(description="Set template name for arc scoring")] = None,
    target_duration_min: Annotated[
        int | None, Field(description="Target set duration in minutes")
    ] = None,
    version_label: Annotated[
        str | None, Field(description="Version label, e.g. 'v2-peak-hour'")
    ] = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> SetVersionResult:
    """Persist an AI-curated track order as a set version — no optimizer runs.

    Workflow: get_candidate_pool → preview_set_arc → commit_set_version.
    The AI selects and orders the tracks; this tool only saves the decision
    and computes a quality_score via arc preview for reference.
    """
    dj_set, version, quality = await svc.commit_version(
        name=name,
        track_ids=track_ids,
        set_id=set_id,
        template=template,
        target_duration_min=target_duration_min,
        version_label=version_label,
    )
    return SetVersionResult(
        set_id=dj_set.id,
        version_id=version.id,
        version_label=version.label,
        track_count=len(track_ids),
        quality_score=round(quality, 4) if quality is not None else None,
        template=template,
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
        Literal["set", "pair", "track_candidates", "subset"],
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
    track_ids: Annotated[
        list[int] | None,
        Field(
            description=(
                "Explicit track ID subset (subset mode). "
                "All directed pairs inside this subset are scored."
            )
        ),
    ] = None,
    top_n: Annotated[
        int,
        Field(description="Max ranked entries returned for subset/track_candidates", ge=1),
    ] = 10,
    count: Annotated[
        int | None,
        Field(description="Alias for top_n (subset/track_candidates)", ge=1),
    ] = None,
    include_transitions: Annotated[
        bool,
        Field(description="Include full transition list in set mode (can be large)"),
    ] = False,
    transitions_limit: Annotated[
        int,
        Field(
            description="Max transitions returned in set mode when include_transitions=true", ge=1
        ),
    ] = 50,
    transitions_offset: Annotated[
        int,
        Field(description="Transition offset for set mode pagination", ge=0),
    ] = 0,
    workflow: BuildSetWorkflow = Depends(get_build_set_workflow),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Scores transitions for a set, a single pair, anchor candidates, or explicit subset and persists results. Use when auditing blends, ranking options, or refreshing stored transition scores."""
    await ctx.report_progress(0, 1, "Scoring transitions")
    effective_top_n = count if count is not None else top_n
    result = await workflow.score_transitions(
        mode=mode,
        set_id=set_id,
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        track_id=track_id,
        track_ids=track_ids,
        top_n=effective_top_n,
        log=ToolContext(ctx),
    )
    # Keep set-mode responses bounded so structured content is not dropped by FastMCP
    # response size limits on large sets.
    if mode in {"set", "subset"}:
        transitions = result.get("transitions")
        if isinstance(transitions, list):
            total = len(transitions)
            if include_transitions:
                page = transitions[transitions_offset : transitions_offset + transitions_limit]
                next_offset = transitions_offset + len(page)
                result["transitions"] = page
                result["transitions_offset"] = transitions_offset
                result["transitions_limit"] = transitions_limit
                result["transitions_total"] = total
                result["transitions_truncated"] = next_offset < total
                result["transitions_next_offset"] = next_offset if next_offset < total else None
            else:
                result.pop("transitions", None)
                result["transitions_included"] = False
                result["transitions_total"] = total
    await ctx.report_progress(1, 1, "Done")
    return result


@tool(
    title="Search Transitions",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def search_transitions(
    limit: Annotated[int, Field(description="Page size", ge=1, le=500)] = 50,
    offset: Annotated[int, Field(description="Pagination offset", ge=0)] = 0,
    sort_by: Annotated[
        str,
        Field(
            description=(
                "Sort fields, comma-separated. Prefix '-' for DESC, '+' for ASC "
                "(example: '+from_bpm,-overall_quality')."
            )
        ),
    ] = "-overall_quality",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Field(description="Fallback direction for sort_by tokens without +/- prefix"),
    ] = "desc",
    sort_direction: Annotated[
        Literal["asc", "desc"] | None,
        Field(
            description=(
                "Alias for sort_order. If provided, overrides sort_order for tokens "
                "without +/- prefix."
            )
        ),
    ] = None,
    filters: Annotated[
        Any,
        Field(
            description=(
                "Filter object: {field: value} for equality or "
                "{field: {op: value}} for advanced operators. "
                "Supported ops: eq, ne, gt, gte, lt, lte, in, not_in, contains, is_null."
            )
        ),
    ] = None,
    include_fields: Annotated[
        Any,
        Field(
            description=(
                "Fields to return (list or comma-separated string). "
                "If omitted, each row contains only ``id`` (use ``all`` or explicit names for full data). "
                "Macros: all, all_transition_fields, all_track_fields, all_feature_fields, "
                "transition_fields, track_fields, feature_fields. "
                "Include ``id`` explicitly when using track/feature macros if you need transition row ids."
            )
        ),
    ] = None,
    exclude_fields: Annotated[
        Any,
        Field(description="Fields to remove from output (list or comma-separated string)."),
    ] = None,
    include_stats: Annotated[
        bool,
        Field(description="Include aggregate statistics over the filtered dataset."),
    ] = True,
    include_field_catalog: Annotated[
        bool,
        Field(
            description=(
                "If true, add ``fields.available``, ``fields.groups``, ``include_macros``, "
                "and top-level ``filter_operators`` (large JSON). Default false for slim MCP replies."
            )
        ),
    ] = False,
    target_quality: Annotated[
        float | None,
        Field(
            description=(
                "Optional target overall quality (0-1). "
                "When provided, response includes feasibility guardrail metadata."
            ),
            ge=0.0,
            le=1.0,
        ),
    ] = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> SearchTransitionsResult:
    """Search scored transition pairs with pagination, filters, sorting, projection, and stats.

    Default rows are ``id`` only; pass ``include_fields`` (or macro ``all``) for wide columns.
    Optional ``target_quality`` adds ``quality_guardrail`` to expose feasibility for a threshold.
    """
    filters_dict = ensure_dict(filters)
    if filters is not None and filters_dict is None:
        raise ValueError("filters must be a JSON object / dict")

    include_list = [str(item) for item in ensure_list(include_fields)] if include_fields else None
    exclude_list = [str(item) for item in ensure_list(exclude_fields)] if exclude_fields else None

    raw = await svc.search_transitions(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_direction=sort_direction,
        filters=filters_dict or {},
        include_fields=include_list,
        exclude_fields=exclude_list,
        include_stats=include_stats,
        include_field_catalog=include_field_catalog,
        target_quality=target_quality,
    )
    return SearchTransitionsResult.model_validate(raw)


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
    svc: SetService = Depends(get_set_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> GetSetCheatSheetResult:
    """Returns a human-readable BPM, key, and energy-arc summary for a set version. Use when reviewing flow on paper or in the booth before playback.

    Structured output includes ``cheat_sheet_lines`` so MCP clients that render JSON
    literally can show line breaks (the ``cheat_sheet`` string may display as ``\\n`` text).
    """
    text, lines = split_multiline_for_json_ui(await svc.get_cheat_sheet(set_id, version=version))
    return GetSetCheatSheetResult(
        set_id=set_id,
        version=version,
        cheat_sheet=text,
        cheat_sheet_lines=lines,
    )


@tool(
    title="Get Set Templates",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
async def get_set_templates() -> GetSetTemplatesResult:
    """Lists registered DJ set templates with slot definitions (moods, BPM, energy). Use when choosing a ``template`` argument for ``commit_set_version`` or comparing archetypes."""
    return GetSetTemplatesResult(
        templates=[
            SetTemplateEntry(
                name=tpl.name,
                duration_min=tpl.duration_min,
                description=tpl.description,
                slots=[
                    SetTemplateSlotRow(
                        position=slot.position,
                        target_mood=slot.target_mood,
                        energy_lufs=slot.energy_lufs,
                        bpm_min=slot.bpm_min,
                        bpm_max=slot.bpm_max,
                        duration_ms=slot.duration_ms,
                        flexibility=slot.flexibility,
                    )
                    for slot in tpl.slots
                ],
            )
            for tpl in TEMPLATES.values()
        ]
    )


@tool(
    title="Preview Set Arc",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def preview_set_arc(
    track_ids: Annotated[
        list[int],
        Field(description="Ordered list of track IDs to evaluate (takes priority over set_id)"),
    ] = [],  # noqa: B006
    set_id: Annotated[
        int | None,
        Field(
            description=(
                "DJ set ID — loads track order from the latest version. "
                "Ignored when track_ids is provided."
            )
        ),
    ] = None,
    template: Annotated[
        str | None,
        Field(
            description="Optional template name (e.g. 'roller_90') for template fitness scoring"
        ),
    ] = None,
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
) -> SetArcPreview:
    """Evaluate a track ordering's fitness without saving a set version.

    Accepts either an explicit ``track_ids`` list or a ``set_id`` that auto-
    loads the latest version's track order.  Runs the same fitness function
    used by build_set, non-destructively.

    Use before committing to an ordering — compare multiple arc shapes and
    identify weak transitions before calling build_set or rebuild_set.

    Returns score (0-1), energy/BPM arcs, weak spot positions, and a
    plain-language recommendation.
    """
    from fastmcp.exceptions import ToolError

    resolved_ids: list[int] = list(track_ids)

    if not resolved_ids and set_id is not None:
        version = await set_repo.get_latest_version(set_id)
        if version is None:
            raise ToolError(f"Set {set_id} has no versions yet")
        resolved_ids = [
            item.track_id for item in sorted(version.items, key=lambda i: i.sort_index)
        ]

    if not resolved_ids:
        return SetArcPreview(
            score=1.0,
            energy_arc=[],
            bpm_arc=[],
            weak_spots=[],
            recommendation="No tracks provided. Pass track_ids or set_id.",
            missing_track_ids=[],
        )

    features_map = await feat_repo.get_scoring_features_batch(resolved_ids)
    scorer = TransitionScorer()
    template_def = TEMPLATES.get(template) if template is not None else None

    result = preview_arc(scorer, features_map, resolved_ids, template=template_def)
    return SetArcPreview(
        score=result.score,
        energy_arc=result.energy_arc,
        bpm_arc=result.bpm_arc,
        weak_spots=result.weak_spots,
        recommendation=result.recommendation,
        missing_track_ids=result.missing_track_ids,
    )
