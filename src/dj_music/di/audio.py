"""Audio-focused dependency factories."""

from __future__ import annotations

from fastmcp.dependencies import Depends

from dj_music.audio.analyzers import AnalyzerRegistry
from dj_music.audio.timeseries import TimeseriesStorage
from dj_music.di.external import get_analyzer_registry, get_ym_client
from dj_music.di.repos import get_audio_repo, get_track_repo
from dj_music.repositories.audio import AudioRepository
from dj_music.repositories.track import TrackRepository
from dj_music.services.audio_service import AudioService
from dj_music.services.tiered_pipeline import TieredPipeline
from dj_music.ym.client import YandexMusicClient


def get_audio_service(
    repo: AudioRepository = Depends(get_audio_repo),  # noqa: B008
    registry: AnalyzerRegistry = Depends(get_analyzer_registry),  # noqa: B008
) -> AudioService:
    """Get AudioService with repository and analyzer registry."""
    return AudioService(repo, registry)


def get_timeseries_storage() -> TimeseriesStorage:
    """Get TimeseriesStorage for frame-level audio data."""
    return TimeseriesStorage()


def get_tiered_pipeline(
    audio_repo: AudioRepository = Depends(get_audio_repo),  # noqa: B008
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    registry: AnalyzerRegistry = Depends(get_analyzer_registry),  # noqa: B008
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    timeseries: TimeseriesStorage = Depends(get_timeseries_storage),  # noqa: B008
) -> TieredPipeline:
    """Get TieredPipeline for level-aware audio analysis."""
    from dj_music.audio.pipeline import AnalysisPipeline

    pipeline = AnalysisPipeline(registry)
    return TieredPipeline(audio_repo, track_repo, pipeline, ym, timeseries=timeseries)
