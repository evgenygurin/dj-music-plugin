"""Tests for error hierarchy."""

from app.core.errors import (
    AnalysisTimeoutError,
    AnalyzerUnavailableError,
    APIError,
    AuthFailedError,
    ConflictError,
    DJMusicError,
    ExportError,
    NotFoundError,
    PipelineError,
    RateLimitedError,
    ValidationError,
    YandexMusicError,
)


def test_hierarchy_base() -> None:
    assert issubclass(NotFoundError, DJMusicError)
    assert issubclass(ValidationError, DJMusicError)
    assert issubclass(ConflictError, DJMusicError)
    assert issubclass(ExportError, DJMusicError)


def test_hierarchy_pipeline() -> None:
    assert issubclass(PipelineError, DJMusicError)
    assert issubclass(AnalyzerUnavailableError, PipelineError)
    assert issubclass(AnalysisTimeoutError, PipelineError)


def test_hierarchy_ym() -> None:
    assert issubclass(YandexMusicError, DJMusicError)
    assert issubclass(RateLimitedError, YandexMusicError)
    assert issubclass(AuthFailedError, YandexMusicError)
    assert issubclass(APIError, YandexMusicError)


def test_not_found_message() -> None:
    err = NotFoundError("Track", 42)
    msg = str(err)
    assert "Track" in msg
    assert "42" in msg


def test_rate_limited_retry_after() -> None:
    err = RateLimitedError(retry_after=5.0)
    assert err.retry_after == 5.0


def test_validation_error_with_details() -> None:
    err = ValidationError("BPM out of range", field="bpm", value=999)
    assert "BPM" in str(err)
    assert err.field == "bpm"
    assert err.value == 999
