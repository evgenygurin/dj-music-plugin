"""YandexAdapter — implements the universal Provider protocol over YandexClient."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from app.providers.yandex.client import YandexClient


class YandexAdapter:
    name: str = "yandex"

    # Source of truth for ``schema://providers/yandex.entities_supported``.
    # Must mirror the entity set handled by ``read`` and ``write`` below;
    # any name added here without a matching ``match`` arm will raise at
    # runtime, and any name handled by the methods but missing here will
    # be invisible to introspection clients.
    entities_supported: ClassVar[tuple[str, ...]] = (
        "track",
        "track_batch",
        "track_similar",
        "album",
        "artist_tracks",
        "playlist",
        "playlist_list",
        "likes",
        "dislikes",
    )

    def __init__(
        self,
        *,
        client: YandexClient,
        download_dir: Path | None = None,
    ) -> None:
        self._client = client
        self._download_dir = download_dir or Path("/tmp/yandex_downloads")

    # ---------- read ---------- #

    async def read(self, entity: str, id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        match entity:
            case "track":
                if id is None:
                    raise ValueError("track read requires id")
                tracks = await self._client.get_tracks([id])
                return tracks[0] if tracks else {}
            case "track_batch":
                ids = params.get("ids", [])
                tracks = await self._client.get_tracks(list(ids))
                return {"tracks": tracks}
            case "track_similar":
                if id is None:
                    raise ValueError("track_similar requires id")
                similar = await self._client.get_similar(id)
                return {"results": similar}
            case "album":
                if id is None:
                    raise ValueError("album read requires id")
                return await self._client.get_album(
                    id, with_tracks=bool(params.get("with_tracks"))
                )
            case "artist_tracks":
                if id is None:
                    raise ValueError("artist_tracks requires id")
                return await self._client.get_artist_tracks(
                    id,
                    offset=int(params.get("offset", 0)),
                    limit=int(params.get("limit", 50)),
                )
            case "playlist":
                if id is None:
                    raise ValueError("playlist read requires id")
                return await self._client.get_playlist(id)
            case "playlist_list":
                return {"playlists": await self._client.list_playlists()}
            case "likes":
                return {"track_ids": await self._client.get_liked_ids()}
            case "dislikes":
                return {"track_ids": await self._client.get_disliked_ids()}
            case _:
                raise ValueError(f"unknown read entity: {entity}")

    # ---------- write ---------- #

    async def write(self, entity: str, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        if entity == "playlist":
            return await self._write_playlist(operation, params)
        if entity == "likes":
            return await self._write_likes(operation, params)
        raise ValueError(f"unknown write entity: {entity}")

    async def _resolve_revision(self, playlist_id: Any, params: dict[str, Any]) -> int:
        """Return params["revision"] when present, else fetch it from YM.

        YM's change-relative endpoint requires the current revision for
        optimistic concurrency. Callers often don't carry it; auto-fetching
        hides that quirk at the adapter boundary.
        """
        raw = params.get("revision")
        if raw is not None:
            return int(raw)
        current = await self._client.get_playlist(playlist_id)
        return int(current.get("revision", 1))

    async def _write_playlist(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        match operation:
            case "create":
                return await self._client.create_playlist(
                    title=params["title"], visibility=params.get("visibility", "private")
                )
            case "rename":
                return await self._client.rename_playlist(
                    params["playlist_id"], title=params["title"]
                )
            case "set_description":
                return await self._client.set_playlist_description(
                    params["playlist_id"], description=params["description"]
                )
            case "delete":
                return await self._client.delete_playlist(params["playlist_id"])
            case "add_tracks":
                pid = params["playlist_id"]
                revision = await self._resolve_revision(pid, params)
                track_ids = [str(t) for t in params["track_ids"]]
                diff = [
                    {
                        "op": "insert",
                        "at": int(params.get("at", 0)),
                        "tracks": [{"id": tid} for tid in track_ids],
                    }
                ]
                return await self._client.modify_playlist(pid, diff=diff, revision=revision)
            case "remove_tracks":
                pid = params["playlist_id"]
                revision = await self._resolve_revision(pid, params)
                diff = [
                    {
                        "op": "delete",
                        "from": int(params["from"]),
                        "to": int(params["to"]),
                    }
                ]
                return await self._client.modify_playlist(pid, diff=diff, revision=revision)
            case _:
                raise ValueError(f"unknown playlist operation: {operation}")

    async def _write_likes(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        track_ids = list(params["track_ids"])
        if operation == "add":
            return await self._client.add_likes(track_ids)
        if operation == "remove":
            return await self._client.remove_likes(track_ids)
        raise ValueError(f"unknown likes operation: {operation}")

    # ---------- search ---------- #

    async def search(self, query: str, type: str = "tracks", limit: int = 20) -> dict[str, Any]:
        return await self._client.search(query=query, type=type, limit=limit)

    # ---------- download ---------- #

    async def download_audio(self, track_id: str, dest: Path | None = None) -> Path:
        target = dest if dest is not None else self._download_dir / f"{track_id}.mp3"
        return await self._client.download_track(track_id, target)

    async def close(self) -> None:
        await self._client.close()
