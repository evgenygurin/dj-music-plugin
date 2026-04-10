"""Audio streaming endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.state import get_runtime

router = APIRouter()


@router.get("/api/audio/stream/{ym_track_id}", tags=["system"])
async def stream_audio(ym_track_id: str, request: Request) -> Any:
    """Proxy-stream a YM track's MP3 bytes to the caller."""
    runtime = get_runtime(request)
    return await runtime.ym_audio_proxy.stream(
        ym_track_id=ym_track_id,
        range_header=request.headers.get("range"),
    )
