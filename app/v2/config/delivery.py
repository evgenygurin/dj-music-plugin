"""Set delivery + export settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeliverySettings(BaseSettings):
    """Deliverable output paths + format toggles."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_DELIVERY_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    output_dir: str = Field(default="generated-sets", description="Root dir for exports.")
    copy_audio_files: bool = Field(default=True)
    emit_m3u8: bool = Field(default=True)
    emit_rekordbox_xml: bool = Field(default=False)
    emit_json_guide: bool = Field(default=True)
    emit_cheatsheet: bool = Field(default=True)
    icloud_min_download_ratio: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Skip copying files whose local size is < ratio * metadata size (icloud stub).",
    )
