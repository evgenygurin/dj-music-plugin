"""Settings facade tests."""

import pytest

from app.config import Settings, get_settings


def test_facade_exposes_all_domains() -> None:
    s = get_settings()
    assert hasattr(s, "database")
    assert hasattr(s, "yandex")
    assert hasattr(s, "audio")
    assert hasattr(s, "transition")
    assert hasattr(s, "optimization")
    assert hasattr(s, "discovery")
    assert hasattr(s, "delivery")
    assert hasattr(s, "mcp")


def test_facade_is_cached() -> None:
    assert get_settings() is get_settings()


def test_settings_construction_without_env() -> None:
    s = Settings()
    assert s.database.database_url.startswith("sqlite")
    assert s.transition.weight_bpm == 0.20


def test_reset_cache_rebuilds_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    first = get_settings()
    assert first.audio.sample_rate == 22050
    monkeypatch.setenv("DJ_AUDIO_SAMPLE_RATE", "44100")
    from app.config import reset_settings_cache

    reset_settings_cache()
    second = get_settings()
    assert second.audio.sample_rate == 44100
    assert second is not first
