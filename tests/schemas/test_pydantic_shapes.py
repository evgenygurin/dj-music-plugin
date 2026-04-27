"""Smoke test that every entity's 4 DTOs exist and validate."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.audio_file import AudioFileCreate
from app.schemas.track import TrackCreate

ENTITIES = [
    "track",
    "playlist",
    "set",
    "audio_file",
    "track_features",
    "transition",
    "transition_history",
    "track_feedback",
    "track_affinity",
    "scoring_profile",
]


@pytest.mark.parametrize("entity", ENTITIES)
def test_four_dtos_importable(entity: str) -> None:
    mod = __import__(f"app.schemas.{entity}", fromlist=["*"])
    camel = "".join(p.capitalize() for p in entity.split("_"))
    for suffix in ("View", "Filter", "Create", "Update"):
        assert hasattr(mod, f"{camel}{suffix}"), f"{entity} missing {camel}{suffix}"


# ── TrackCreate contract ────────────────────────────────────────────────


def test_track_create_minimal_payload_validates() -> None:
    """``external_ids`` is the ONLY required field; ``source`` defaults to ``yandex``."""
    obj = TrackCreate(external_ids=["12345"])
    assert obj.external_ids == ["12345"]
    assert obj.source == "yandex"
    assert obj.playlist_id is None


def test_track_create_with_all_fields() -> None:
    obj = TrackCreate(external_ids=["a", "b"], source="yandex", playlist_id=42)
    assert obj.playlist_id == 42


def test_track_create_rejects_empty_external_ids() -> None:
    with pytest.raises(ValidationError, match="external_ids"):
        TrackCreate(external_ids=[])


def test_track_create_requires_external_ids() -> None:
    with pytest.raises(ValidationError, match="external_ids"):
        TrackCreate()  # type: ignore[call-arg]


def test_track_create_rejects_legacy_provider_ids() -> None:
    """The pre-PR field name was ``provider_ids``. ``extra='forbid'`` must
    reject it so future reverts surface as a Pydantic error, not a silent
    drop on the wire.
    """
    with pytest.raises(ValidationError, match="provider_ids"):
        TrackCreate(external_ids=["1"], provider_ids=["2"])  # type: ignore[call-arg]


def test_track_create_rejects_handler_ignored_fields() -> None:
    """``title`` / ``duration_ms`` / ``status`` were removed because the
    handler unconditionally pulls them from provider metadata. Schema
    must reject them so callers don't silently believe they took effect.
    """
    for stray in ("title", "sort_title", "duration_ms", "status"):
        with pytest.raises(ValidationError, match=stray):
            TrackCreate(external_ids=["1"], **{stray: "x"})  # type: ignore[arg-type]


# ── AudioFileCreate xor invariant ───────────────────────────────────────


def test_audio_file_create_single_form() -> None:
    obj = AudioFileCreate(track_id=42)
    assert obj.track_id == 42
    assert obj.track_ids is None
    assert obj.source == "yandex"


def test_audio_file_create_batch_form() -> None:
    obj = AudioFileCreate(track_ids=[1, 2, 3])
    assert obj.track_id is None
    assert obj.track_ids == [1, 2, 3]


def test_audio_file_create_rejects_both_forms() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        AudioFileCreate(track_id=1, track_ids=[2, 3])


def test_audio_file_create_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        AudioFileCreate()


def test_audio_file_create_rejects_empty_batch() -> None:
    with pytest.raises(ValidationError, match="track_ids"):
        AudioFileCreate(track_ids=[])
