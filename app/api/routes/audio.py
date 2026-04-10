"""Audio streaming endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.api.state import get_runtime

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/audio/stream/{ym_track_id}", tags=["system"])
async def stream_audio(ym_track_id: str, request: Request) -> Any:
    """Proxy-stream a YM track's MP3 bytes to the caller."""
    runtime = get_runtime(request)
    return await runtime.ym_audio_proxy.stream(
        ym_track_id=ym_track_id,
        range_header=request.headers.get("range"),
    )


@router.get("/api/audio/downbeat/{track_id}", tags=["system"])
async def get_or_compute_downbeat(track_id: int, request: Request) -> dict[str, Any]:
    """Return first_downbeat_ms, computing on-the-fly if not yet in DB.

    TODO: Remove this endpoint after beatgrid migration completes
    and all tracks have first_downbeat_ms populated.
    """
    runtime = get_runtime(request)

    # 1. Check DB first
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings

    db_url = settings.database_url.replace(":6543/", ":5432/")
    engine = create_async_engine(db_url, connect_args={"statement_cache_size": 0})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        r = await session.execute(
            text(
                "SELECT f.first_downbeat_ms, f.bpm, e.external_id "
                "FROM track_audio_features_computed f "
                "JOIN track_external_ids e ON e.track_id = f.track_id "
                "AND e.platform = 'yandex_music' "
                "WHERE f.track_id = :tid"
            ),
            {"tid": track_id},
        )
        row = r.fetchone()

    await engine.dispose()

    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    first_downbeat_ms, bpm, ym_track_id = row

    # Already computed — return cached
    if first_downbeat_ms is not None:
        return {"track_id": track_id, "first_downbeat_ms": first_downbeat_ms, "cached": True}

    if not bpm or bpm <= 0:
        return {"track_id": track_id, "first_downbeat_ms": 0.0, "cached": False}

    # 2. Compute on-the-fly: download 200KB, detect downbeat
    try:
        proxy = runtime.ym_audio_proxy
        signed_url = await proxy.get_signed_url(str(ym_track_id))
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(signed_url, headers={"Range": "bytes=0-200000"})
            if resp.status_code not in (200, 206):
                return {"track_id": track_id, "first_downbeat_ms": 0.0, "cached": False}
            audio_bytes = resp.content
    except Exception as exc:
        logger.warning("Downbeat compute: download failed for track %d: %s", track_id, exc)
        return {"track_id": track_id, "first_downbeat_ms": 0.0, "cached": False}

    # Run detection in thread pool (numpy CPU work)
    from scripts.migrate_beatgrids import detect_first_downbeat_ms

    downbeat_ms = await asyncio.to_thread(detect_first_downbeat_ms, audio_bytes, bpm)
    if downbeat_ms is None:
        downbeat_ms = 0.0

    # 3. Save to DB for future requests
    try:
        engine2 = create_async_engine(db_url, connect_args={"statement_cache_size": 0})
        async_session2 = sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)
        async with async_session2() as session:
            await session.execute(
                text(
                    "UPDATE track_audio_features_computed "
                    "SET first_downbeat_ms = :val WHERE track_id = :tid"
                ),
                {"val": round(downbeat_ms, 2), "tid": track_id},
            )
            await session.commit()
        await engine2.dispose()
    except Exception as exc:
        logger.warning("Downbeat compute: DB save failed for track %d: %s", track_id, exc)

    return {"track_id": track_id, "first_downbeat_ms": round(downbeat_ms, 2), "cached": False}
