"""Application configuration via environment variables.

All tunable values live here. Use `settings.*` everywhere — no magic numbers.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DJ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ─────��────────────────────────────────
    database_url: str = "postgresql+asyncpg://localhost:5432/dj_music"

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
    pagination_size: int = 100  # Must be >= total tools (45) for Claude Code compat
    pagination_max: int = 100
    cache_dir: str = "cache/"
    mcp_retry_attempts: int = 3
    mcp_retry_delay: float = 1.0  # seconds
    payload_logging: bool = False
    debug: bool = False

    # ── Logging ──────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    log_to_client_debug: bool = False

    # ── Transition Scoring ────────────────────────────
    transition_cache_ttl: int = 3600  # seconds
    transition_cache_max_size: int = 10_000
    transition_hard_reject_bpm_diff: float = 10.0
    transition_hard_reject_camelot_dist: int = 5
    transition_hard_reject_energy_gap: float = 6.0  # LUFS

    # ── P3 Scoring Thresholds ─────────────────────────
    scoring_bpm_confidence_floor: float = 0.5  # below this, BPM score reduced
    scoring_variable_tempo_penalty: float = 0.15  # penalty for variable tempo tracks
    scoring_lra_diff_penalty_threshold: float = 8.0  # LU difference for penalty
    scoring_lra_diff_penalty: float = 0.10  # penalty amount
    scoring_crest_diff_penalty_threshold: float = 10.0  # dB difference for penalty
    scoring_crest_diff_penalty: float = 0.10  # penalty amount
    scoring_energy_slope_bonus: float = 0.05  # bonus for same slope direction

    # ── Storage Backends ─────────────────────────────
    storage_backend: str = "memory"  # memory, file, redis
    storage_file_dir: str = "cache/storage"
    storage_redis_host: str = "localhost"
    storage_redis_port: int = 6379
    storage_redis_password: str = ""
    storage_redis_db: int = 0
    response_cache_enabled: bool = True
    response_cache_ttl: int = 300  # seconds

    # ── Discovery & Expansion ────────────────────────
    discovery_min_duration_ms: int = 180_000  # 3 min
    discovery_max_duration_ms: int = 600_000  # 10 min
    discovery_batch_size: int = 20  # tracks per YM add_tracks batch
    discovery_max_seeds: int = 30  # max seed tracks for playlist expansion
    discovery_bad_genres: str = (
        "pop,ruspop,dance,house,trance,rap,foreignrap,rnb,"
        "dubstep,dnb,classical,jazz,country,metal,rock"
    )
    discovery_bad_version_words: str = (
        "radio,edit,acoustic,instrumental,a cappella,live,"
        "stripped,clean,remix,rework,bootleg,extended mix,continuous,dub version"
    )

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
    # ── Tiered Analysis ───────────────────────────────
    audio_triage_workers: int = 6  # parallel workers for L1+L2
    audio_scoring_workers: int = 4  # parallel workers for L3
    audio_download_workers: int = 8  # parallel download threads for L4

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

    # ── Audit Thresholds ──────────────────────────────
    audit_true_peak_max: float = -0.3  # dB
    audit_bpm_confidence_min: float = 0.5
    audit_key_confidence_min: float = 0.4
    audit_hp_ratio_max: float = 8.0
    audit_crest_factor_max: float = 30.0  # dB
    audit_spectral_flatness_max: float = 0.5

    # ── Mood Classifier ───────────────────────────────
    mood_catch_all_penalty: float = 0.85
    mood_confidence_threshold: float = 0.3

    # ── Delivery ──────────────────────────────────────
    delivery_output_dir: str = "generated-sets/"
    delivery_icloud_stub_threshold: float = 0.9  # blocks/size ratio

    # ── LLM Sampling ─────────────────────────────────
    # Optional: only needed for server-side sampling (ctx.sample() fallback).
    # Claude Code MAX users don't need this — Claude generates queries directly
    # and passes them to tools via search_queries parameter (client-driven mode).
    anthropic_api_key: str = ""
    sampling_model: str = "claude-sonnet-4-5"
    sampling_max_tokens: int = 512
    sampling_temperature: float = 0.8

    # ── Background Tasks ─────────────────────────────
    docket_url: str = "memory://"
    docket_concurrency: int = 4
    task_poll_interval_seconds: int = 5

    # ── Observability ────────────────────────────────
    sentry_dsn: str = ""
    otel_enabled: bool = False
    otel_service_name: str = "dj-music"
    otel_endpoint: str = ""

    @property
    def is_dev(self) -> bool:
        return self.debug


settings = Settings()
