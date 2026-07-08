"""Structured-output models for set delivery."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeliverSetResult(BaseModel):
    version_id: int
    out_dir: str
    files: list[str] = Field(default_factory=list)
    track_count: int = 0
    m3u8: bool = False
    rekordbox_xml: bool = False
    json_guide: bool = False
    cheatsheet: bool = False
    continuous_mix: bool = False
