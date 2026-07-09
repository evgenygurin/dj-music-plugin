"""Track features repository — batch load for scoring + targeted mood writes."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.models.track_features import TrackAudioFeaturesComputed, TrackSection
from app.repositories.base import BaseRepository
from app.shared.constants import SectionType
from app.shared.errors import NotFoundError
from app.shared.features import TrackFeatures

# Vector / array columns stored as JSON-encoded strings in Postgres
# (model declares them as ``Mapped[str | None]`` over ``String(...)``).
# The pipeline returns them as ``list[float]`` / ``list[int]`` — encode
# on the way in so handlers can splat ``**result.features`` without
# per-column serialization gymnastics.
_JSON_ENCODED_VECTOR_COLUMNS = frozenset(
    {
        "mfcc_vector",
        "tonnetz_vector",
        "tempogram_ratio_vector",
        "beat_loudness_band_ratio",
        "phrase_boundaries_ms",
    }
)

_MIX_IN_SECTION_PRIORITY = (
    SectionType.INTRO,
    SectionType.ATTACK,
    SectionType.SUSTAIN,
    SectionType.AMBIENT,
    SectionType.RISE,
)
_MIX_OUT_SECTION_PRIORITY = (
    SectionType.OUTRO,
    SectionType.SUSTAIN,
    SectionType.AMBIENT,
    SectionType.BREAKDOWN,
    SectionType.VALLEY,
)


def _serialize_vectors(values: dict[str, Any]) -> dict[str, Any]:
    """Encode list-typed vector columns as JSON strings; pass others through.

    Pipeline analyzers historically return ``np.ndarray`` from some code
    paths and ``list[float]`` from others. ``json.dumps`` rejects ndarray
    with an opaque ``TypeError`` deep in the encoder — coerce via
    ``.tolist()`` first so a future analyzer that forgets the explicit
    conversion still produces a valid JSON string instead of crashing
    the entire L3 sweep on its first track.
    """
    out = dict(values)
    for col in _JSON_ENCODED_VECTOR_COLUMNS:
        if col not in out or out[col] is None or isinstance(out[col], str):
            continue
        value = out[col]
        # ndarray / tuple → list, then JSON-encode. ``hasattr(... "tolist")``
        # catches numpy without forcing a numpy import in this leaf module.
        if hasattr(value, "tolist") and not isinstance(value, list):
            value = value.tolist()
        elif isinstance(value, tuple):
            value = list(value)
        out[col] = json.dumps(value)
    return out


def _preferred_section(
    sections: list[TrackSection],
    priority: tuple[SectionType, ...],
    *,
    fallback_last: bool,
) -> TrackSection | None:
    if not sections:
        return None
    by_type: dict[int, list[TrackSection]] = {}
    for section in sections:
        by_type.setdefault(section.section_type, []).append(section)
    for section_type in priority:
        candidates = by_type.get(int(section_type))
        if candidates:
            return min(candidates, key=lambda section: section.start_ms)
    return sections[-1] if fallback_last else sections[0]


def _phrase_anchor(features: TrackFeatures, section: TrackSection) -> int:
    boundaries = features.phrase_boundaries_ms or []
    inside = [boundary for boundary in boundaries if section.start_ms <= boundary < section.end_ms]
    return inside[0] if inside else section.start_ms


class TrackFeaturesRepository(BaseRepository[TrackAudioFeaturesComputed]):
    model = TrackAudioFeaturesComputed

    async def get_by_track_id(self, track_id: int) -> TrackAudioFeaturesComputed | None:
        """Return the features row for ``track_id`` (primary key), or None."""
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id == track_id
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    async def upsert(self, *, track_id: int, **values: Any) -> TrackAudioFeaturesComputed:
        """INSERT or UPDATE the features row for ``track_id``.

        Used by the analyze handler after pipeline completion. Only whitelists
        columns that exist on the model to tolerate pipeline extras, and
        JSON-encodes list-valued vector columns so callers can splat
        ``**result.features`` (which contains raw ``list[float]`` vectors)
        directly into the upsert without manual serialization.
        """
        allowed = {c.key for c in TrackAudioFeaturesComputed.__table__.columns}
        clean = _serialize_vectors(
            {k: v for k, v in values.items() if k in allowed and k != "track_id"}
        )
        existing = await self.get_by_track_id(track_id)
        if existing is not None:
            for key, val in clean.items():
                setattr(existing, key, val)
            await self.session.flush()
            return existing
        row = TrackAudioFeaturesComputed(track_id=track_id, **clean)
        self.session.add(row)
        await self.session.flush()
        return row

    async def upsert_analysis(self, *, track_id: int, **values: Any) -> TrackAudioFeaturesComputed:
        """Persist audio analysis without clobbering canonical provider data."""
        existing = await self.get_by_track_id(track_id)
        clean = dict(values)

        source_fields = (
            ("bpm", "audio_bpm", "bpm_source"),
            ("bpm_confidence", "audio_bpm_confidence", "bpm_source"),
            ("key_code", "audio_key_code", "key_source"),
            ("key_confidence", "audio_key_confidence", "key_source"),
            ("mood", "audio_mood", "mood_source"),
        )
        for canonical, audio, source in source_fields:
            if canonical not in clean:
                continue
            clean[audio] = clean[canonical]
            if existing is not None and getattr(existing, source, None) == "beatport":
                clean.pop(canonical)
            else:
                clean[source] = "audio"

        if "mood_confidence" in clean:
            clean["audio_mood_confidence"] = clean["mood_confidence"]
            if existing is not None and getattr(existing, "mood_source", None) == "beatport":
                clean.pop("mood_confidence")

        return await self.upsert(track_id=track_id, **clean)

    async def get_scoring_features_batch(self, track_ids: list[int]) -> dict[int, TrackFeatures]:
        """Batch load scoring features as TrackFeatures dataclasses (JSON vectors parsed)."""
        if not track_ids:
            return {}
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id.in_(track_ids)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        result = {r.track_id: TrackFeatures.from_db(r) for r in rows}

        section_stmt = (
            select(TrackSection)
            .where(TrackSection.track_id.in_(result))
            .order_by(TrackSection.track_id, TrackSection.start_ms)
        )
        section_rows = (await self.session.execute(section_stmt)).scalars().all()
        sections_by_track: dict[int, list[TrackSection]] = {}
        for section in section_rows:
            sections_by_track.setdefault(section.track_id, []).append(section)

        for track_id, features in result.items():
            sections = sections_by_track.get(track_id, [])
            mix_in = _preferred_section(
                sections,
                _MIX_IN_SECTION_PRIORITY,
                fallback_last=False,
            )
            mix_out = _preferred_section(
                sections,
                _MIX_OUT_SECTION_PRIORITY,
                fallback_last=True,
            )
            if mix_in is not None:
                features.mix_in_section_id = mix_in.id
                features.mix_in_section_type = mix_in.section_type
                features.mix_in_point_ms = _phrase_anchor(features, mix_in)
            if mix_out is not None:
                features.mix_out_section_id = mix_out.id
                features.mix_out_section_type = mix_out.section_type
                features.mix_out_point_ms = _phrase_anchor(features, mix_out)
        return result

    async def set_mood(self, track_id: int, *, mood: str, confidence: float) -> None:
        """Store audio mood while preserving a verified Beatport canonical mood."""
        row = await self.get_by_track_id(track_id)
        if row is None:
            raise NotFoundError("track_features", track_id)
        row.audio_mood = mood
        row.audio_mood_confidence = confidence
        if row.mood_source != "beatport":
            row.mood = mood
            row.mood_confidence = confidence
            row.mood_source = "audio"
        await self.session.flush()

    async def get_analysis_level(self, track_id: int) -> int:
        """Return current analysis_level (0 if no row)."""
        stmt = select(TrackAudioFeaturesComputed.analysis_level).where(
            TrackAudioFeaturesComputed.track_id == track_id
        )
        row = await self.session.scalar(stmt)
        return int(row) if row is not None else 0

    async def save_track_section(self, track_id: int, section_data: dict) -> TrackSection:
        section = TrackSection(
            track_id=track_id,
            section_type=section_data.get("section_type", 10),
            start_ms=section_data["start_ms"],
            end_ms=section_data["end_ms"],
            energy=section_data.get("energy"),
            confidence=section_data.get("confidence"),
        )
        for col in ("lufs", "spectral_centroid"):
            if col in section_data:
                setattr(section, col, section_data[col])
        if "stem_energy" in section_data:
            section.stem_energy = section_data["stem_energy"]
        self.session.add(section)
        await self.session.flush()
        return section

    async def get_track_sections(self, track_id: int) -> list[dict]:
        stmt = (
            select(TrackSection)
            .where(TrackSection.track_id == track_id)
            .order_by(TrackSection.start_ms)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [
            {
                "id": r.id,
                "section_type": r.section_type,
                "start_ms": r.start_ms,
                "end_ms": r.end_ms,
                "energy": r.energy,
                "lufs": getattr(r, "lufs", None),
                "spectral_centroid": getattr(r, "spectral_centroid", None),
                "stem_energy": getattr(r, "stem_energy", None),
            }
            for r in rows
        ]
