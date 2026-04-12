# Re-export shim for backward compatibility
# NOTE: explicit re-exports instead of sys.modules swap to avoid double-import
# class identity issues when dj_music.core.errors is imported first.
from dj_music.core.errors import (  # noqa: F401
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
