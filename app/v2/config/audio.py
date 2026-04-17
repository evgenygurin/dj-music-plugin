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
