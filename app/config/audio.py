"""Audio analysis pipeline settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AudioSettings(BaseSettings):
    """Audio loader + analyzer configuration (librosa / essentia)."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_AUDIO_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    sample_rate: int = Field(default=22050, ge=8000, le=48000)
    mfcc_coefficients: int = Field(default=13, ge=1, le=40)
    hop_length: int = Field(default=512, ge=128, le=4096)
    n_fft: int = Field(default=2048, ge=256, le=8192)
    process_pool_workers: int = Field(default=2, ge=0, le=16)
    process_worker_cache_size: int = Field(default=4, ge=1, le=32)
    clip_duration_s: float = Field(default=60.0, ge=10.0, le=300.0)
    clip_window_count: int = Field(default=3, ge=1, le=10)
    clip_window_fade_ms: float = Field(default=20.0, ge=0.0, le=200.0)

    # Cache directory root — used by timeseries storage (legacy default preserved).
    cache_dir: str = Field(default="cache/")

    # Mood classifier catch-all subgenre penalty. Multiplies the score of the
    # catch-all subgenres (driving + hypnotic) so a clear specific-subgenre
    # match wins ties — they accept a broad feature range and should be a
    # fallback, not a default.
    #
    # Was 0.85: in the classifier's low-margin regime (median winner-vs-runner
    # margin ~5%) a 15% haircut acted as an ABSOLUTE filter, zeroing `driving`
    # across the whole 24k library (diag: scripts/diag_mood_classifier.py).
    # 0.97 keeps the fallback bias while letting `driving` win on merit
    # (~1.7% of the library) instead of never. NOTE: this does not make
    # `hypnotic` appear — its profile loses on the current (L2) feature set
    # regardless of the penalty; that needs the classifier redesign, not a
    # constant.
    mood_catch_all_penalty: float = Field(default=0.97, ge=0.0, le=1.0)
