"""Normalize legacy analyzer payloads into domain contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.analysis import BeatGrid, BeatPosition, CuePoint, Phrase, Section, TempoHypothesis


def tempo_hypotheses(raw: Sequence[Mapping[str, Any]]) -> tuple[TempoHypothesis, ...]:
    return tuple(
        TempoHypothesis(
            bpm=float(item["bpm"]),
            confidence=float(item.get("confidence", 0.0)),
            source=str(item.get("source", "legacy")),
        )
        for item in raw
    )


def beatgrid(raw: Mapping[str, Any]) -> BeatGrid:
    beats = tuple(
        BeatPosition(
            float(item["time_s"]), int(item["index"]), bool(item.get("is_downbeat", False))
        )
        for item in raw.get("beats", ())
    )
    return BeatGrid(
        bpm=float(raw["bpm"]),
        beats=beats,
        beats_per_bar=int(raw.get("beats_per_bar", 4)),
        phase_s=float(raw.get("phase_s", 0.0)),
    )


def phrases(raw: Sequence[Mapping[str, Any]]) -> tuple[Phrase, ...]:
    return tuple(Phrase(**item) for item in raw)


def sections(raw: Sequence[Mapping[str, Any]]) -> tuple[Section, ...]:
    return tuple(Section(**item) for item in raw)


def cues(raw: Sequence[Mapping[str, Any]]) -> tuple[CuePoint, ...]:
    return tuple(CuePoint(**item) for item in raw)
