"""Beatport provider settings.

Beatport is used as a *ground-truth metadata* source: human-curated genre /
sub-genre plus authored BPM and Camelot key. Auth is the Serato-DJ-Lite
OAuth code flow (username + password → access/refresh token). Audio download
needs a paid Beatport Streaming Professional subscription and is therefore
NOT relied upon — only catalog metadata, which works on a free account.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BeatportSettings(BaseSettings):
    """Beatport v4 API credentials + tuning."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_BEATPORT_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    username: str = Field(default="", description="Beatport account; if empty, provider is off.")
    password: str = Field(default="", description="Beatport password.")
    # Public client id embedded in Serato DJ Lite — the same one orpheusdl uses.
    client_id: str = Field(default="Zy2K9Wvy6DkUds7g8s1GNMHfk17E5Ch2BWHlyaGY")
    redirect_uri: str = Field(default="seratodjlite://beatport")
    base_url: str = Field(default="https://api.beatport.com/v4")
    rate_limit_delay_s: float = Field(default=0.3, ge=0.0, le=30.0)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    timeout_s: float = Field(default=30.0, ge=1.0, le=120.0)
    # Matcher gates — a candidate is a confident match only when the audio
    # signals we already computed agree with Beatport's authored values.
    match_bpm_tolerance: float = Field(default=1.5, ge=0.0, le=10.0)
    match_duration_tolerance_ms: int = Field(default=3000, ge=0, le=60000)
    # Best-effort Beatport genre lookup during track_features analyze/reanalyze.
    # OFF by default: the beatport_* columns must exist in the DB first
    # (see app/models/track_features.py). Flip on via DJ_BEATPORT_ENRICH_ON_ANALYZE=true
    # once the columns are applied, otherwise the enrich upsert aborts the
    # analyze transaction on a DB missing those columns.
    enrich_on_analyze: bool = Field(default=False)

    @property
    def enabled(self) -> bool:
        return bool(self.username and self.password)
