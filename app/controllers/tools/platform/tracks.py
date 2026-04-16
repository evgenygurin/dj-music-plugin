"""Platform track and artist-track tools."""

from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_track_repo
from app.controllers.dependencies.external import get_music_provider
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ICON_YM,
    TOOL_META,
    ToolCategory,
)
from app.controllers.tools.platform._constants import MAX_BATCH_TRACKS, MAX_SEARCH_LIMIT
from app.core.constants import Provider
from app.core.utils.parsing import ensure_list
from app.db.repositories.track import TrackRepository
from app.providers.models import ProviderTrack
from app.providers.protocol import MusicProvider
from app.schemas.platform_responses import (
    ArtistTrackItem,
    ArtistTracksPage,
    PlatformTrackBatch,
    PlatformTrackIdMapItem,
    PlatformTrackIdMapResult,
)

ArtistSortBy = Literal["date", "popularity"]
PlatformName = Literal["yandex_music", "spotify", "beatport", "soundcloud"]
_PAGE_SIZE = 20


@tool(
    title="Platform Get Tracks",
    tags={ToolCategory.PLATFORM.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def get_platform_tracks(
    track_ids: Annotated[
        str | list[str],
        Field(
            description="Platform track ID or comma-separated IDs (e.g. '12345' or ['12345','67890'])"
        ),
    ],
    fields: Annotated[
        str,
        Field(
            description="Comma-separated field names to return, or 'all' for full data",
            examples=["id,title,artists,albums,duration_ms", "all"],
        ),
    ] = "id,title,artists,albums,duration_ms",
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> PlatformTrackBatch:
    """Batch-load platform tracks by ID with optional field projection."""
    ids = ensure_list(track_ids)
    if not ids:
        raise ToolError("track_ids required")
    if len(ids) > MAX_BATCH_TRACKS:
        raise ToolError(f"Maximum {MAX_BATCH_TRACKS} track IDs per request")

    tracks: list[ProviderTrack] = []
    unresolved_ids: list[str] = []
    try:
        tracks = await provider.get_tracks(ids)
        returned_ids = {track.id for track in tracks}
        unresolved_ids = [track_id for track_id in ids if track_id not in returned_ids]
    except Exception:
        # Fallback for providers that fail the whole batch on a single bad ID.
        for track_id in ids:
            try:
                one_track = await provider.get_tracks([track_id])
            except Exception:
                unresolved_ids.append(track_id)
                continue
            match = next((track for track in one_track if track.id == track_id), None)
            if match is None:
                unresolved_ids.append(track_id)
                continue
            tracks.append(match)

    if fields == "all":
        tracks_data = [t.model_dump() for t in tracks]
    else:
        wanted = {f.strip() for f in fields.split(",")}
        tracks_data = [{k: v for k, v in t.model_dump().items() if k in wanted} for t in tracks]
    error_message: str | None = None
    if unresolved_ids:
        sample = ", ".join(unresolved_ids[:10])
        error_message = f"Some platform track_ids could not be loaded: {sample}"
    return PlatformTrackBatch(
        requested=len(ids),
        count=len(tracks_data),
        unresolved_track_ids=unresolved_ids,
        error=error_message,
        tracks=tracks_data,
    )


@tool(
    title="Platform Artist Tracks",
    tags={ToolCategory.PLATFORM.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def get_platform_artist_tracks(
    artist_id: Annotated[str, Field(description="Platform artist ID (string)")],
    offset: Annotated[int, Field(description="Number of tracks to skip", ge=0)] = 0,
    limit: Annotated[int, Field(description="Max tracks to return", ge=1, le=100)] = _PAGE_SIZE,
    sort_by: Annotated[ArtistSortBy, Field(description="Sort order")] = "date",
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> ArtistTracksPage:
    """Return a paginated slice of tracks for a platform artist."""
    page = offset // limit
    tracks = await provider.get_artist_tracks(artist_id, page=page)

    page_slice = tracks[offset % limit :] if offset % limit else tracks
    page_slice = page_slice[:limit]

    return ArtistTracksPage(
        artist_id=artist_id,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        count=len(page_slice),
        tracks=[
            ArtistTrackItem(
                id=t.id,
                title=t.title,
                duration_ms=t.duration_ms,
                albums=[{"id": t.album_id, "title": t.album_title, "genre": t.album_genre}]
                if t.album_id
                else [],
            )
            for t in page_slice
        ],
        has_next=len(tracks) >= MAX_SEARCH_LIMIT,
    )


@tool(
    title="Resolve Platform Track IDs",
    tags={ToolCategory.PLATFORM.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_YM,
    meta=TOOL_META,
)
async def resolve_platform_track_ids(
    track_ids: Annotated[
        list[int],
        Field(description="Ordered local track IDs to resolve against external platform IDs"),
    ],
    platform: Annotated[
        PlatformName, Field(description="Target platform namespace")
    ] = Provider.YANDEX_MUSIC.value,
    strict: Annotated[
        bool,
        Field(
            description=(
                "If true, mark response with strict_violation/error when at least one "
                "local track has no mapping on the selected platform"
            )
        ),
    ] = False,
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
) -> PlatformTrackIdMapResult:
    """Resolve local DB track IDs to platform track IDs using persistent mappings."""
    if not track_ids:
        raise ToolError("track_ids required")

    mapping = await track_repo.resolve_local_ids_to_platform(track_ids, platform=platform)

    unresolved = [track_id for track_id in track_ids if track_id not in mapping]
    strict_violation = bool(strict and unresolved)
    error_message: str | None = None
    if strict_violation:
        missing = ", ".join(str(track_id) for track_id in unresolved[:10])
        error_message = f"Missing {platform} mapping for track_ids: {missing}"

    items = [
        PlatformTrackIdMapItem(
            local_track_id=track_id,
            platform_track_id=mapping.get(track_id),
            found=track_id in mapping,
        )
        for track_id in track_ids
    ]
    return PlatformTrackIdMapResult(
        platform=platform,
        requested=len(track_ids),
        resolved=len(track_ids) - len(unresolved),
        unresolved_track_ids=unresolved,
        strict_violation=strict_violation,
        error=error_message,
        mappings=items,
    )
