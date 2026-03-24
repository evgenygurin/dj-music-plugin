"""SQLAlchemy models — import all to register with Base.metadata."""

from app.models.audio import (  # noqa: F401
    Embedding,
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
from app.models.base import Base, TimestampMixin  # noqa: F401
from app.models.export import AppExport  # noqa: F401
from app.models.ingestion import (  # noqa: F401
    ProviderModel,
    ProviderTrackId,
    RawProviderResponse,
)
from app.models.key import Key, KeyEdge  # noqa: F401
from app.models.library import (  # noqa: F401
    DjBeatgrid,
    DjBeatgridChangePoint,
    DjCuePoint,
    DjLibraryItem,
    DjSavedLoop,
)
from app.models.platform import (  # noqa: F401
    BeatportMetadata,
    SoundcloudMetadata,
    SpotifyAlbumMetadata,
    SpotifyArtistMetadata,
    SpotifyAudioFeatures,
    SpotifyMetadata,
    SpotifyPlaylistMetadata,
    YandexMetadata,
)
from app.models.playlist import Playlist, PlaylistItem  # noqa: F401
from app.models.set import (  # noqa: F401
    DjSet,
    SetConstraint,
    SetFeedback,
    SetItem,
    SetVersion,
)
from app.models.track import (  # noqa: F401
    Artist,
    Genre,
    Label,
    Release,
    Track,
    TrackArtist,
    TrackExternalId,
    TrackGenre,
    TrackLabel,
    TrackRelease,
)
from app.models.transition import Transition, TransitionCandidate  # noqa: F401
