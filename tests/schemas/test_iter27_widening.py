"""Audit iter 27: AudioFileUpdate (bitrate/sample_rate/channels) +
SetVersionFilter id range lookups."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.audio_file import AudioFileUpdate
from app.schemas.set import SetVersionFilter


def test_audio_file_update_accepts_bitrate_etc() -> None:
    AudioFileUpdate.model_validate({"bitrate": 320})
    AudioFileUpdate.model_validate({"sample_rate": 44100})
    AudioFileUpdate.model_validate({"channels": 2})


def test_audio_file_update_rejects_out_of_range() -> None:
    """Each numeric field is bounded - bitrate <= 2000 kbps,
    sample_rate <= 384 kHz, channels <= 8."""
    with pytest.raises(ValidationError):
        AudioFileUpdate.model_validate({"bitrate": 99999})
    with pytest.raises(ValidationError):
        AudioFileUpdate.model_validate({"channels": 100})


def test_set_version_filter_accepts_id_range_lookups() -> None:
    SetVersionFilter.model_validate({"id__gt": 60})
    SetVersionFilter.model_validate({"id__gte": 1})
    SetVersionFilter.model_validate({"id__lt": 100})
    SetVersionFilter.model_validate({"id__lte": 99})
