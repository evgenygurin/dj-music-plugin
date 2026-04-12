"""SQLAlchemy models — import all to register with Base.metadata."""

from dj_music.models.audio import (  # noqa: F401
    Embedding,
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
from dj_music.models.base import Base, TimestampMixin  # noqa: F401
from dj_music.models.export import AppExport  # noqa: F401
from dj_music.models.ingestion import (  # noqa: F401
    ProviderModel,
    RawProviderResponse,
)
from dj_music.models.key import Key, KeyEdge  # noqa: F401
from dj_music.models.library import (  # noqa: F401
    DjBeatgrid,
    DjBeatgridChangePoint,
    DjCuePoint,
    DjLibraryItem,
    DjSavedLoop,
)
from dj_music.models.platform import (  # noqa: F401
    BeatportMetadata,
    SoundcloudMetadata,
    SpotifyAlbumMetadata,
    SpotifyArtistMetadata,
    SpotifyAudioFeatures,
    SpotifyMetadata,
    SpotifyPlaylistMetadata,
    YandexMetadata,
)
from dj_music.models.playlist import Playlist, PlaylistItem  # noqa: F401
from dj_music.models.set import (  # noqa: F401
    DjSet,
    SetConstraint,
    SetFeedback,
    SetItem,
    SetVersion,
)
from dj_music.models.track import (  # noqa: F401
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
from dj_music.models.transition import Transition, TransitionCandidate  # noqa: F401
