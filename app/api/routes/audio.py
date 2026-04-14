"""Audio streaming endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from app.api.state import get_runtime

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/audio/stream/{track_id}", tags=["system"])
async def stream_audio(track_id: str, request: Request) -> Any:
    """Proxy-stream a track's MP3 bytes to the caller."""
    runtime = get_runtime(request)
    return await runtime.audio_proxy.stream(
        track_id=track_id,
        range_header=request.headers.get("range"),
    )
