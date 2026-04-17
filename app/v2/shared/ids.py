"""Type aliases for entity identifiers.

These are NewType wrappers — they behave as ``int`` at runtime but are
distinct types for static type checking. Using ``TrackId`` vs plain ``int``
prevents accidentally passing a ``PlaylistId`` where a ``TrackId`` was expected.
"""

from __future__ import annotations

from typing import NewType

TrackId = NewType("TrackId", int)
PlaylistId = NewType("PlaylistId", int)
SetId = NewType("SetId", int)
SetVersionId = NewType("SetVersionId", int)
SetItemId = NewType("SetItemId", int)
AudioFileId = NewType("AudioFileId", int)
TransitionId = NewType("TransitionId", int)
TransitionHistoryId = NewType("TransitionHistoryId", int)
TrackFeedbackId = NewType("TrackFeedbackId", int)
TrackAffinityId = NewType("TrackAffinityId", int)
ScoringProfileId = NewType("ScoringProfileId", int)
ArtistId = NewType("ArtistId", int)
GenreId = NewType("GenreId", int)
ReleaseId = NewType("ReleaseId", int)
KeyCode = NewType("KeyCode", int)  # 0-23 per Camelot

# Provider-side identifiers are strings (yandex ID, spotify ID, ...)
ProviderTrackId = NewType("ProviderTrackId", str)
ProviderAlbumId = NewType("ProviderAlbumId", str)
ProviderArtistId = NewType("ProviderArtistId", str)
ProviderPlaylistId = NewType("ProviderPlaylistId", str)
