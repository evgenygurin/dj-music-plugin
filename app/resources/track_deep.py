from __future__ import annotations

import asyncio
import json
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.errors import NotFoundError


@resource(
    "local://tracks/{id}/deep_features{?stem}",
    mime_type="application/json",
    tags={"core", "entity:track", "view:deep_analysis"},
)
async def track_deep_features(
    id: int,
    stem: str = "original",
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    features = await uow.stem_features.get_all_for_track(id)
    stems_data: dict[str, Any] = {}
    for row in features:
        cols = {
            c.name: getattr(row, c.name)
            for c in row.__table__.columns
            if c.name not in ("id", "track_id", "pipeline_run_id", "created_at", "updated_at")
        }
        stems_data[row.stem_name] = {k: v for k, v in cols.items() if v is not None}

    if stem != "original" and stem not in stems_data:
        raise NotFoundError("stem", f"{stem} for track {id}")

    payload: dict[str, Any] = {
        "track_id": id,
        "stems": stems_data if stem == "original" else {stem: stems_data.get(stem)},
    }
    return json.dumps(payload, default=str)


@resource(
    "local://tracks/{id}/structure",
    mime_type="application/json",
    tags={"core", "entity:track", "view:structure"},
)
async def track_structure(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    sections = await uow.track_features.get_track_sections(id)
    return json.dumps({"track_id": id, "sections": sections}, default=str)


@resource(
    "local://tracks/{id}/waveform{?stem}",
    mime_type="application/json",
    tags={"core", "entity:track", "view:waveform"},
)
async def track_waveform(
    id: int,
    stem: str = "original",
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    from supabase import create_client

    from app.config.supabase import SupabaseSettings

    settings = SupabaseSettings()
    prefix = f"{id}" if stem == "original" else f"{id}/stem_{stem}"
    if not settings.supabase_url or not settings.supabase_service_key:
        return b"".decode()
    client = create_client(settings.supabase_url, settings.supabase_service_key)
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        None,
        lambda: client.storage.from_("track-waveforms").download(f"{prefix}/waveform.json"),
    )
    return data.decode()
