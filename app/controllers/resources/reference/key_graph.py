"""Reference resource exposing key graph data from DB tables."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceResult, resource
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session
from app.controllers.resources._shared import json_resource
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_REFERENCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.db.models.key import Key, KeyEdge


@resource(
    uri="reference://key-graph",
    name="Key Compatibility Graph",
    title="Key Compatibility Graph",
    description="Key nodes and weighted compatibility edges from the key graph tables",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def key_graph_reference(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Return key graph nodes + edge distribution from DB."""
    key_rows = await session.execute(
        select(
            Key.key_code,
            Key.camelot,
            Key.name,
            Key.pitch_class,
            Key.mode,
        ).order_by(Key.key_code)
    )
    keys = [
        {
            "key_code": row.key_code,
            "camelot": row.camelot,
            "name": row.name,
            "pitch_class": row.pitch_class,
            "mode": row.mode,
        }
        for row in key_rows
    ]

    edge_rows = await session.execute(
        select(
            KeyEdge.from_key_code,
            KeyEdge.to_key_code,
            KeyEdge.distance,
            KeyEdge.weight,
            KeyEdge.rule_name,
        ).order_by(KeyEdge.from_key_code, KeyEdge.to_key_code)
    )
    edges = [
        {
            "from_key_code": row.from_key_code,
            "to_key_code": row.to_key_code,
            "distance": row.distance,
            "weight": row.weight,
            "rule_name": row.rule_name,
        }
        for row in edge_rows
    ]

    distance_rows = await session.execute(
        select(KeyEdge.distance, func.count(KeyEdge.id))
        .group_by(KeyEdge.distance)
        .order_by(KeyEdge.distance)
    )
    distance_distribution = {int(distance): int(count) for distance, count in distance_rows}

    data = {
        "total_keys": len(keys),
        "total_edges": len(edges),
        "distance_distribution": distance_distribution,
        "keys": keys,
        "edges": edges,
    }
    return json_resource(data)
