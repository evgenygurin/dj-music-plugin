from __future__ import annotations

import io

import numpy as np

from app.providers.supabase.storage_client import SupabaseStorageClient


async def upload_timeseries(
    storage: SupabaseStorageClient,
    track_id: int,
    stem_name: str,
    data: dict[str, np.ndarray],
) -> None:
    for name, arr in data.items():
        buf = io.BytesIO()
        np.savez_compressed(buf, data=arr)
        buf.seek(0)

        prefix = f"{track_id}" if stem_name == "original" else f"{track_id}/stem_{stem_name}"
        await storage.upload(
            bucket="track-timeseries",
            path=f"{prefix}/{name}.npz",
            data=buf.read(),
        )
