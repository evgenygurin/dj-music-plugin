"""SQLAlchemy models — import all to register with Base.metadata."""

from app.db.models.audio import (  # noqa: F401
    Embedding,
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
from app.db.models.base import Base, TimestampMixin  # noqa: F401
from app.db.models.export import AppExport  # noqa: F401
from app.db.models.ingestion import (  # noqa: F401
    ProviderModel,
    RawProviderResponse,
)
from app.db.models.key import Key, KeyEdge  # noqa: F401
from app.db.models.library import (  # noqa: F401
    DjBeatgrid,
    DjBeatgridChangePoint,
    DjCuePoint,
    DjLibraryItem,
    DjSavedLoop,
)
from app.db.models.platform import (  # noqa: F401
    BeatportMetadata,
    SoundcloudMetadata,
    SpotifyAlbumMetadata,
    SpotifyArtistMetadata,
    SpotifyAudioFeatures,
    SpotifyMetadata,
    SpotifyPlaylistMetadata,
    YandexMetadata,
)
from app.db.models.playlist import Playlist, PlaylistItem  # noqa: F401
from app.db.models.set import (  # noqa: F401
    DjSet,
    SetConstraint,
    SetFeedback,
    SetItem,
    SetVersion,
)
from app.db.models.track import (  # noqa: F401
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
from app.db.models.transition import Transition, TransitionCandidate  # noqa: F401
