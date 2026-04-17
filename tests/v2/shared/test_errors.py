"""Error hierarchy tests."""

from app.v2.shared.errors import (
    ConflictError,
    DJMusicError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
)


def test_base_error_is_exception() -> None:
    assert issubclass(DJMusicError, Exception)


def test_not_found_formats_message() -> None:
    err = NotFoundError("track", 42)
    assert err.entity_type == "track"
    assert err.identifier == 42
    assert "track" in str(err)
    assert "42" in str(err)


def test_not_found_subclasses_base() -> None:
    assert issubclass(NotFoundError, DJMusicError)


def test_validation_error_keeps_details() -> None:
    err = ValidationError("bpm must be in [20, 300]", details={"field": "bpm", "value": 500})
    assert err.details == {"field": "bpm", "value": 500}
    assert "bpm must be in [20, 300]" in str(err)


def test_conflict_error_message() -> None:
    err = ConflictError("track with yandex_id=12345 already exists")
    assert "12345" in str(err)
    assert isinstance(err, DJMusicError)


def test_not_allowed_error_holds_context() -> None:
    err = NotAllowedError(entity="track", operation="delete")
    assert err.entity == "track"
    assert err.operation == "delete"
    assert "track" in str(err)
    assert "delete" in str(err)
