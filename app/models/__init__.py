"""v2 ORM models."""

from app.models.audio_file import DjBeatgrid, DjLibraryItem
from app.models.base import Base, TimestampMixin
from app.models.key import Key, KeyEdge
from app.models.playlist import DjPlaylist, DjPlaylistItem
from app.models.provider_metadata import Provider, RawProviderResponse, YandexMetadata
from app.models.scoring_profile import ScoringProfile
from app.models.set import DjSet, DjSetItem, DjSetVersion
from app.models.track import (
    Artist,
    Genre,
    Release,
    Track,
    TrackArtist,
    TrackExternalId,
    TrackGenre,
    TrackRelease,
)
from app.models.track_affinity import TrackAffinity
from app.models.track_features import (
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
from app.models.track_feedback import TrackFeedback
from app.models.transition import Transition
from app.models.transition_history import TransitionHistory

__all__ = [
    "Artist",
    "Base",
    "DjBeatgrid",
    "DjLibraryItem",
    "DjPlaylist",
    "DjPlaylistItem",
    "DjSet",
    "DjSetItem",
    "DjSetVersion",
    "FeatureExtractionRun",
    "Genre",
    "Key",
    "KeyEdge",
    "Provider",
    "RawProviderResponse",
    "Release",
    "ScoringProfile",
    "TimeseriesReference",
    "TimestampMixin",
    "Track",
    "TrackAffinity",
    "TrackArtist",
    "TrackAudioFeaturesComputed",
    "TrackExternalId",
    "TrackFeedback",
    "TrackGenre",
    "TrackRelease",
    "TrackSection",
    "Transition",
    "TransitionHistory",
    "YandexMetadata",
]
