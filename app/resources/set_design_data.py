"""Full labeled data-dump of one set/version, for a design agent building
the next-gen set-building dashboard. Read-only, no mutation, no Prefab UI.

Throwaway-by-design: once the design agent proposes a layout, this
resource's shape is expected to be revisited (folded into ``ui_control_center``,
split into proper resources, or removed). See
docs/superpowers/specs/2026-07-07-set-design-data-dump-design.md.
"""

from __future__ import annotations

import itertools
import json
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.repositories.unit_of_work import UnitOfWork
from app.resources._feature_catalog import (
    TRACK_FEATURE_CATALOG,
    TRANSITION_FEATURE_CATALOG,
    describe_field,
)
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.tools.ui.render_studio import gather_render_studio

_SET_FIELDS = (
    "id",
    "name",
    "description",
    "target_duration_ms",
    "target_bpm_min",
    "target_bpm_max",
    "target_energy_arc",
    "template_name",
    "source_playlist_id",
    "ym_playlist_id",
)
_VERSION_FIELDS = ("id", "set_id", "label", "generator_run_meta", "quality_score")

_ITEM_FIELDS = (
    "transition_id",
    "out_section_id",
    "in_section_id",
    "mix_in_point_ms",
    "mix_out_point_ms",
    "planned_eq",
    "notes",
    "pinned",
)


async def _build_tracks_block(
    uow: UnitOfWork, version_id: int
) -> tuple[list[dict[str, Any]], list[int]]:
    items = await uow.set_versions.get_items(version_id)
    if not items:
        return [], []

    sorted_items = sorted(items, key=lambda i: i.sort_index)
    track_ids = [item.track_id for item in sorted_items]
    tracks_by_id = await uow.tracks.get_many(track_ids)
    features_page = await uow.track_features.filter(
        where={"track_id__in": track_ids}, limit=max(len(track_ids), 1)
    )
    features_by_track_id = {row.track_id: row for row in features_page.items}

    rows: list[dict[str, Any]] = []
    for item in sorted_items:
        track = tracks_by_id.get(item.track_id)
        feature_row = features_by_track_id.get(item.track_id)
        features: dict[str, Any] = {}
        if feature_row is not None:
            for name in TRACK_FEATURE_CATALOG:
                if not hasattr(feature_row, name):
                    continue
                features[name] = describe_field(
                    TRACK_FEATURE_CATALOG, name, getattr(feature_row, name)
                )
        rows.append(
            {
                "position": item.sort_index,
                "track_id": item.track_id,
                "title": getattr(track, "title", None),
                **{field: getattr(item, field) for field in _ITEM_FIELDS},
                "features": features,
            }
        )
    return rows, track_ids


async def _build_transitions_block(
    uow: UnitOfWork, sorted_track_ids: list[int]
) -> list[dict[str, Any]]:
    if len(sorted_track_ids) < 2:
        return []

    pairs = list(itertools.pairwise(sorted_track_ids))
    transitions_by_pair = await uow.transitions.get_pairs_batch(pairs)

    edges: list[dict[str, Any]] = []
    for from_id, to_id in pairs:
        row = transitions_by_pair.get((from_id, to_id))
        if row is None:
            continue
        scores = {
            name: describe_field(TRANSITION_FEATURE_CATALOG, name, getattr(row, name))
            for name in TRANSITION_FEATURE_CATALOG
            if hasattr(row, name)
        }
        edges.append({"from_track_id": from_id, "to_track_id": to_id, "scores": scores})
    return edges


@resource(
    "local://sets/{id}/design_data{?version}",
    mime_type="application/json",
    tags={"core", "namespace:library", "entity:set", "view:design_data"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_design_data(
    id: int,
    version: int | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Labeled dump of a set + its latest (or pinned) version, for design work."""
    dj_set = await uow.sets.get(id)
    if dj_set is None:
        raise NotFoundError("set", id)

    if version is not None:
        ver = await uow.set_versions.get(version)
    else:
        ver = await uow.set_versions.get_latest(id)
    if ver is None or getattr(ver, "set_id", None) != id:
        raise NotFoundError("set_version", version or f"latest(set={id})")

    tracks, sorted_track_ids = await _build_tracks_block(uow, ver.id)
    payload: dict[str, Any] = {
        "set": {field: getattr(dj_set, field) for field in _SET_FIELDS},
        "version": {field: getattr(ver, field) for field in _VERSION_FIELDS},
        "tracks": tracks,
        "transitions": await _build_transitions_block(uow, sorted_track_ids),
        "render": await gather_render_studio(uow, version_id=ver.id, job_id=None),
    }
    return json.dumps(payload, default=str)
