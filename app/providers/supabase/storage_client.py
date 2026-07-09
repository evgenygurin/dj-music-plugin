from __future__ import annotations

import asyncio
from typing import Any

from supabase import create_client


class SupabaseStorageClient:
    def __init__(self, url: str, key: str) -> None:
        self._available = bool(url and key)
        if self._available:
            self._client = create_client(url, key)

    @property
    def available(self) -> bool:
        return self._available

    async def upload(self, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> Any:
        if not self._available:
            return None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._client.storage.from_(bucket).upload(
                path, data, {"content-type": content_type}
            ),
        )

    async def download(self, bucket: str, path: str) -> bytes:
        if not self._available:
            return b""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._client.storage.from_(bucket).download(path),
        )
