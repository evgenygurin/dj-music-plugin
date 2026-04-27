"""Audit iter 39 (T-37): same drift class on the Set + AudioFile
schemas — View dropped persisted columns, Update dropped fields
that Create accepted, Filter dropped canonical id range queries.

Set:
* ``SetUpdate`` could not retarget ``target_bpm_min`` /
  ``target_bpm_max`` / ``source_playlist_id`` even though
  ``SetCreate`` accepted them — callers had to delete + recreate.
* ``SetFilter`` rejected ``id__gt/gte/lt/lte`` (``set_version``
  has them; consistency drift).

AudioFile:
* 4 persisted columns were invisible on the View — ``file_uri``
  (file:// scheme), ``file_hash`` (sha256 dedup),
  ``mime_type`` (REQUIRED on the model), ``source_app``.
* ``AudioFileFilter`` could not lookup any of them.
* ``AudioFileUpdate`` could not write any of them — re-running
  dedup or relocating the source app required delete + recreate.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.audio_file import AudioFileFilter, AudioFileUpdate, AudioFileView
from app.schemas.set import SetFilter, SetUpdate


class TestSetFilterIdRange:
    @pytest.mark.parametrize("op", ["gt", "gte", "lt", "lte"])
    def test_id_range_lookups(self, op: str) -> None:
        SetFilter.model_validate({f"id__{op}": 100})


class TestSetUpdateAcceptsNewlyMutableFields:
    def test_target_bpm_min_round_trips(self) -> None:
        upd = SetUpdate.model_validate({"target_bpm_min": 124})
        assert upd.target_bpm_min == 124

    def test_target_bpm_max_round_trips(self) -> None:
        upd = SetUpdate.model_validate({"target_bpm_max": 132})
        assert upd.target_bpm_max == 132

    def test_source_playlist_id_round_trips(self) -> None:
        upd = SetUpdate.model_validate({"source_playlist_id": 42})
        assert upd.source_playlist_id == 42

    @pytest.mark.parametrize("field,bad", [("target_bpm_min", 50), ("target_bpm_max", 300)])
    def test_bpm_validators_match_create(self, field: str, bad: int) -> None:
        """SetUpdate must mirror SetCreate's ge=60/le=250 validation."""
        with pytest.raises(ValidationError):
            SetUpdate.model_validate({field: bad})


class TestAudioFileViewExposesPersistedColumns:
    def test_file_uri_round_trips(self) -> None:
        view = AudioFileView.model_validate(
            {
                "id": 1,
                "track_id": 10,
                "file_path": "/x/y.mp3",
                "file_size": 100,
                "file_uri": "file:///x/y.mp3",
            }
        )
        assert view.file_uri == "file:///x/y.mp3"

    def test_file_hash_round_trips(self) -> None:
        sha = "a" * 64
        view = AudioFileView.model_validate(
            {
                "id": 1,
                "track_id": 10,
                "file_path": "/x/y.mp3",
                "file_size": 100,
                "file_hash": sha,
            }
        )
        assert view.file_hash == sha

    def test_mime_type_round_trips(self) -> None:
        view = AudioFileView.model_validate(
            {
                "id": 1,
                "track_id": 10,
                "file_path": "/x/y.mp3",
                "file_size": 100,
                "mime_type": "audio/mpeg",
            }
        )
        assert view.mime_type == "audio/mpeg"

    def test_source_app_round_trips(self) -> None:
        view = AudioFileView.model_validate(
            {
                "id": 1,
                "track_id": 10,
                "file_path": "/x/y.mp3",
                "file_size": 100,
                "source_app": "yandex_music",
            }
        )
        assert view.source_app == "yandex_music"

    def test_new_fields_default_none(self) -> None:
        view = AudioFileView.model_validate(
            {"id": 1, "track_id": 10, "file_path": "/a", "file_size": 1}
        )
        for f in ("file_uri", "file_hash", "mime_type", "source_app"):
            assert getattr(view, f) is None


class TestAudioFileFilterNewLookups:
    def test_file_uri_icontains(self) -> None:
        AudioFileFilter.model_validate({"file_uri__icontains": "yandex"})

    def test_file_hash_eq(self) -> None:
        AudioFileFilter.model_validate({"file_hash__eq": "deadbeef"})

    def test_file_hash_isnull(self) -> None:
        AudioFileFilter.model_validate({"file_hash__isnull": True})

    def test_mime_type_eq(self) -> None:
        AudioFileFilter.model_validate({"mime_type__eq": "audio/mpeg"})

    def test_mime_type_in(self) -> None:
        AudioFileFilter.model_validate({"mime_type__in": ["audio/mpeg", "audio/flac"]})

    def test_source_app_eq(self) -> None:
        AudioFileFilter.model_validate({"source_app__eq": "yandex_music"})

    def test_source_app_in(self) -> None:
        AudioFileFilter.model_validate({"source_app__in": ["yandex_music", "spotify"]})

    def test_source_app_isnull(self) -> None:
        AudioFileFilter.model_validate({"source_app__isnull": True})


class TestAudioFileUpdateNewlyMutable:
    def test_file_uri_round_trips(self) -> None:
        upd = AudioFileUpdate.model_validate({"file_uri": "file:///x/y.mp3"})
        assert upd.file_uri == "file:///x/y.mp3"

    def test_file_hash_round_trips(self) -> None:
        sha = "b" * 64
        upd = AudioFileUpdate.model_validate({"file_hash": sha})
        assert upd.file_hash == sha

    def test_mime_type_round_trips(self) -> None:
        upd = AudioFileUpdate.model_validate({"mime_type": "audio/flac"})
        assert upd.mime_type == "audio/flac"

    def test_source_app_round_trips(self) -> None:
        upd = AudioFileUpdate.model_validate({"source_app": "rekordbox"})
        assert upd.source_app == "rekordbox"

    def test_max_length_enforced(self) -> None:
        """Mirror the model's max_length constraints (file_uri 1000,
        file_hash 128, mime_type 50, source_app 100)."""
        with pytest.raises(ValidationError):
            AudioFileUpdate.model_validate({"mime_type": "x" * 51})


class TestUnknownLookupStillRejected:
    def test_set_filter(self) -> None:
        with pytest.raises(ValidationError):
            SetFilter.model_validate({"name__startswith": "x"})

    def test_audio_filter(self) -> None:
        with pytest.raises(ValidationError):
            AudioFileFilter.model_validate({"file_path__startswith": "x"})
