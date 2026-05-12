"""Handler for entity_create(entity="track", data={source, external_ids, ...}).

Fetches metadata via provider, inserts Track + YandexMetadata + TrackExternalId,
idempotent by provider_id (skips existing). Optionally links to playlist.

Progress reporting: one tick per imported ref.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context

from app.handlers._context_log import safe_info
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork


async def track_import_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    registry: ProviderRegistry,
) -> dict[str, Any]:
    source = data.get("source", "yandex")
    external_ids: list[str] = [str(x) for x in data["external_ids"]]
    playlist_id: int | None = data.get("playlist_id")

    provider = registry.get(source)

    # Idempotency: look up existing local tracks by provider id.
    existing_map = await uow.tracks.batch_get_by_provider_ids(source, external_ids)

    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    id_mapping: dict[str, int] = {}
    errors: list[dict[str, Any]] = []

    total = len(external_ids)
    for i, ext_id in enumerate(external_ids):
        if ext_id in existing_map:
            row = existing_map[ext_id]
            skipped.append({"external_id": ext_id, "local_id": row.id})
            id_mapping[ext_id] = row.id
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        try:
            meta = await provider.read("track", id=ext_id, params={})
        except Exception as exc:
            errors.append({"external_id": ext_id, "error": str(exc)})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        track_row = await uow.tracks.create(
            title=meta.get("title", "Untitled"),
            duration_ms=meta.get("durationMs"),
            sort_title=(meta.get("title") or "").lower(),
        )
        album = (meta.get("albums") or [{}])[0]
        await uow.yandex_metadata.upsert(
            track_id=track_row.id,
            yandex_track_id=ext_id,
            album_id=str(album["id"]) if album.get("id") is not None else None,
            album_title=album.get("title"),
            album_genre=album.get("genre"),
            album_year=album.get("year"),
            duration_ms=meta.get("durationMs"),
            cover_uri=meta.get("coverUri"),
            explicit=bool(meta.get("explicit", False)),
        )
        await uow.tracks.ensure_external_id(
            track_id=track_row.id, platform=source, external_id=ext_id
        )

        imported.append({"external_id": ext_id, "local_id": track_row.id})
        id_mapping[ext_id] = track_row.id

        if playlist_id is not None:
            await uow.playlists.append_tracks(playlist_id=playlist_id, track_ids=[track_row.id])

        await ctx.report_progress(progress=i + 1, total=total)

    await safe_info(
        ctx,
        f"track_import: {len(imported)} imported, {len(skipped)} skipped, {len(errors)} errors",
    )

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "id_mapping": id_mapping,
    }
