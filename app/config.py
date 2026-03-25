"""Application configuration via environment variables.

All tunable values live here. Use `settings.*` everywhere — no magic numbers.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DJ_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # ── Database ──────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///dj_music.db"

    # ── Yandex Music ──────────────────────────────────
    ym_token: str = ""
    ym_user_id: str = ""
    ym_base_url: str = "https://api.music.yandex.net"
    ym_library_path: str = ""
    ym_rate_limit_delay: float = 1.5  # seconds between YM API calls
    ym_retry_attempts: int = 3
    ym_retry_backoff_factor: float = 2.0  # exponential backoff multiplier

    # ── MCP Server ────────────────────────────────────
    server_name: str = "DJ Music"
    pagination_size: int = 20
    pagination_max: int = 100
    cache_dir: str = "cache/"
    mcp_retry_attempts: int = 3
    mcp_retry_delay: float = 1.0  # seconds
    payload_logging: bool = False
    debug: bool = False

    # ── Transition Scoring ────────────────────────────
    transition_cache_ttl: int = 3600  # seconds
    transition_cache_max_size: int = 10_000
    transition_hard_reject_bpm_diff: float = 10.0
    transition_hard_reject_camelot_dist: int = 5
    transition_hard_reject_energy_gap: float = 6.0  # LUFS

    # ── GA Optimizer ──────────────────────────────────
    ga_population_size: int = 100
    ga_max_generations: int = 200
    ga_mutation_rate: float = 0.15
    ga_elitism_rate: float = 0.05
    ga_tournament_size: int = 3
    ga_convergence_threshold: int = 20  # generations without improvement

    # ── Audio Analysis ────────────────────────────────
    audio_analysis_timeout: float = 120.0  # per-track seconds
    audio_batch_timeout: float = 600.0
    audio_stem_timeout: float = 300.0
    audio_hop_length: int = 512
    audio_sample_rate: int = 22050
    audio_mfcc_n_coeffs: int = 13

    # ── Techno Quality Criteria ───────────────────────
    techno_bpm_min: float = 120.0
    techno_bpm_max: float = 155.0
    techno_lufs_min: float = -20.0
    techno_lufs_max: float = -4.0
    techno_energy_min: float = 0.05
    techno_onset_rate_min: float = 1.0
    techno_kick_prominence_min: float = 0.05
    techno_pulse_clarity_min: float = 0.02
    techno_hp_ratio_max: float = 8.0
    techno_centroid_min: float = 300.0  # Hz
    techno_centroid_max: float = 10_000.0  # Hz
    techno_flatness_max: float = 0.5
    techno_tempo_confidence_min: float = 0.3
    techno_bpm_stability_min: float = 0.3
    techno_crest_factor_max: float = 30.0  # dB
    techno_lra_max: float = 25.0  # LU
    techno_hnr_min: float = -30.0  # dB

    # ── Mood Classifier ───────────────────────────────
    mood_catch_all_penalty: float = 0.85
    mood_confidence_threshold: float = 0.3

    # ── Delivery ──────────────────────────────────────
    delivery_output_dir: str = "generated-sets/"
    delivery_icloud_stub_threshold: float = 0.9  # blocks/size ratio

    # ── LLM Sampling ─────────────────────────────────
    sampling_model: str = "claude-sonnet-4-5"
    sampling_max_tokens: int = 512
    sampling_temperature: float = 0.8

    # ── Observability ─────────────────────────────────
    # NOTE: SENTRY_DSN and OTEL_* vars don't use DJ_ prefix (standard env var names)
    sentry_dsn: str = ""  # Will be read from SENTRY_DSN env var
    otel_enabled: bool = False  # DJ_OTEL_ENABLED - explicitly enable OTEL
    otel_service_name: str = "dj-music"  # OTEL_SERVICE_NAME override
    otel_endpoint: str = ""  # OTEL_EXPORTER_OTLP_ENDPOINT override

    @property
    def is_dev(self) -> bool:
        return self.debug

    model_config = SettingsConfigDict(
        env_prefix="DJ_",
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow specific env vars without DJ_ prefix
        extra="allow",  # Allow SENTRY_DSN, OTEL_* without validation
    )


settings = Settings()
