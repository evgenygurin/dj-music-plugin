"""act_build — UI action: re-optimize a version's tracks into a new set_version."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.set_version_build import set_version_build_handler
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_optimizer, get_transition_scorer, get_uow
from app.shared.errors import NotFoundError
from app.tools.compute.sequence_optimize import sequence_optimize

try:
    from fastmcp.apps import AppConfig, app_config_to_meta_dict
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "act_build requires fastmcp[apps]. Install with: uv sync --all-extras."
    ) from _exc


async def _run_sequence_optimize(**kwargs: Any) -> Any:
    """Seam for tests — forwards to the real sequence_optimize tool function."""
    return await sequence_optimize(**kwargs)


@tool(
    name="act_build",
    tags={"namespace:ui:read", "ui"},
    annotations={"readOnlyHint": False, "idempotentHint": False},
    meta={
        "ui": True,
        "timeout_s": 300.0,
        **app_config_to_meta_dict(AppConfig(visibility=["app"])),
    },
    description=(
        "UI action: re-optimize a set version's tracks and persist a new "
        "version. Called from the UI only."
    ),
    timeout=300.0,
)
async def act_build(
    version_id: Annotated[int, Field(ge=1, description="Source set version ID")],
    algorithm: Annotated[str, Field(description="ga | greedy | auto")] = "auto",
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    optimizer_builder: Any = Depends(get_optimizer),
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    ver = await uow.set_versions.get(version_id)
    if ver is None:
        raise NotFoundError("set_version", version_id)

    items = await uow.set_versions.get_items(version_id)
    track_ids = [it.track_id for it in sorted(items, key=lambda i: i.sort_index)]

    opt = await _run_sequence_optimize(
        track_ids=track_ids,
        algorithm=algorithm,
        template=None,
        pinned=None,
        excluded=None,
        uow=uow,
        scorer=scorer,
        optimizer_builder=optimizer_builder,
        ctx=ctx,
    )

    created = await set_version_build_handler(
        ctx,
        uow,
        {
            "set_id": ver.set_id,
            "label": f"ui-rebuild-{opt.algorithm}",
            "track_order": list(opt.track_order),
            "quality_score": opt.quality_score,
        },
    )
    # The real handler returns the created id under ``version_id``; older
    # callers/stubs may use ``id`` — accept both.
    new_version_id = created.get("version_id", created.get("id"))
    return {
        "new_version_id": new_version_id,
        "quality_score": created.get("quality_score", opt.quality_score),
        "algorithm": opt.algorithm,
        "n_tracks": len(track_ids),
    }
