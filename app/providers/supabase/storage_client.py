from __future__ import annotations

import asyncio
from typing import Any

from supabase import create_client


class SupabaseStorageClient:
    def __init__(self, url: str, key: str) -> None:
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
        self._client = create_client(url, key)

    async def upload(self, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._client.storage.from_(bucket).upload(
                path, data, {"content-type": content_type}
            ),
        )

    async def download(self, bucket: str, path: str) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._client.storage.from_(bucket).download(path),
        )
