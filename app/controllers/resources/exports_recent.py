"""Recent export history resource."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceResult, resource
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.controllers.dependencies import get_db_session
from app.controllers.resources._shared import json_resource
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_RESOURCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.db.models.export import AppExport
from app.db.models.playlist import Playlist


@resource(
    uri="exports://recent{?limit}",
    name="Recent Exports",
    title="Recent Exports",
    description="Recent export jobs with playlist context, formats, and output metadata",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def exports_recent(
    limit: Annotated[int, "Max recent rows"] = 20,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Return recent export rows ordered by most-recent first."""
    page_limit = max(1, min(limit, settings.pagination_max))
    rows = await session.execute(
        select(
            AppExport.id,
            AppExport.target_app,
            AppExport.export_format,
            AppExport.playlist_id,
            Playlist.name.label("playlist_name"),
            AppExport.file_path,
            AppExport.file_size,
            AppExport.created_at,
            AppExport.updated_at,
        )
        .outerjoin(Playlist, Playlist.id == AppExport.playlist_id)
        .order_by(AppExport.created_at.desc())
        .limit(page_limit)
    )

    exports = [
        {
            "id": row.id,
            "target_app": row.target_app,
            "export_format": row.export_format,
            "playlist": (
                {"id": row.playlist_id, "name": row.playlist_name}
                if row.playlist_id is not None
                else None
            ),
            "file_path": row.file_path,
            "file_size": row.file_size,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]

    data = {
        "limit": page_limit,
        "returned": len(exports),
        "exports": exports,
    }
    return json_resource(data)
