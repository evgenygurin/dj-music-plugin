"""Compatibility shim — re-exports platform_responses under legacy YM names.

Remove this file after Phase 3 when all controllers are updated.
"""

from app.schemas.platform_responses import (
    AlbumResult as YMAlbumResponse,
)
from app.schemas.platform_responses import (
    ArtistTrackItem as YMArtistTrackItem,
)
from app.schemas.platform_responses import (
    ArtistTracksPage as YMArtistTracksPage,
)
from app.schemas.platform_responses import (
    LikesActionResult as YMLikesActionResult,
)
from app.schemas.platform_responses import (
    PlatformSearchResult as YMSearchResponse,
)
from app.schemas.platform_responses import (
    PlatformTrackBatch as YMTrackBatch,
)
from app.schemas.platform_responses import (
    PlaylistActionResult as YMPlaylistActionResult,
)

__all__ = [
    "YMAlbumResponse",
    "YMArtistTrackItem",
    "YMArtistTracksPage",
    "YMLikesActionResult",
    "YMPlaylistActionResult",
    "YMSearchResponse",
    "YMTrackBatch",
]
