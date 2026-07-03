"""Map verified Beatport metadata onto the application's canonical fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.shared.constants import CAMELOT_KEYS, TechnoSubgenre

_CAMELOT_TO_KEY_CODE = {notation: code for code, (notation, _name) in CAMELOT_KEYS.items()}

_DIRECT_GENRE_MAP: dict[str, TechnoSubgenre] = {
    "hard techno": TechnoSubgenre.HARD_TECHNO,
    "hard dance / hardcore / neo rave": TechnoSubgenre.HARD_TECHNO,
    "minimal / deep tech": TechnoSubgenre.MINIMAL,
    "melodic house & techno": TechnoSubgenre.MELODIC_DEEP,
    "progressive house": TechnoSubgenre.PROGRESSIVE,
    "acid": TechnoSubgenre.ACID,
    "breaks / breakbeat / uk bass": TechnoSubgenre.BREAKBEAT,
    "electro (classic / detroit / modern)": TechnoSubgenre.DETROIT,
}

_SUBGENRE_HINTS: tuple[tuple[str, TechnoSubgenre], ...] = (
    ("hard techno", TechnoSubgenre.HARD_TECHNO),
    ("neo rave", TechnoSubgenre.HARD_TECHNO),
    ("industrial", TechnoSubgenre.INDUSTRIAL),
    ("psy-techno", TechnoSubgenre.DRIVING),
    ("peak time", TechnoSubgenre.PEAK_TIME),
    ("driving", TechnoSubgenre.DRIVING),
    ("melodic techno", TechnoSubgenre.MELODIC_DEEP),
    ("deep tech", TechnoSubgenre.MINIMAL),
    ("progressive psy", TechnoSubgenre.PROGRESSIVE),
    ("raw", TechnoSubgenre.RAW),
    ("hypnotic", TechnoSubgenre.HYPNOTIC),
    ("dub techno", TechnoSubgenre.DUB_TECHNO),
    ("ambient", TechnoSubgenre.AMBIENT_DUB),
    ("acid", TechnoSubgenre.ACID),
    ("tribal", TechnoSubgenre.TRIBAL),
    ("breakbeat", TechnoSubgenre.BREAKBEAT),
    ("detroit", TechnoSubgenre.DETROIT),
    ("minimal", TechnoSubgenre.MINIMAL),
    ("progressive", TechnoSubgenre.PROGRESSIVE),
    ("melodic", TechnoSubgenre.MELODIC_DEEP),
)


@dataclass(frozen=True, slots=True)
class CanonicalMood:
    value: str
    confidence: float


def beatport_key_code(camelot: str | None) -> int | None:
    """Convert a Beatport Camelot label to the internal 0-23 key code."""
    if not camelot:
        return None
    return _CAMELOT_TO_KEY_CODE.get(camelot.strip().upper())


def beatport_bpm_agrees(
    beatport_bpm: float | None,
    audio_bpm: float | None,
) -> bool:
    """Accept authored BPM only when it agrees with audio, including octave errors."""
    if beatport_bpm is None:
        return False
    if audio_bpm is None:
        return True
    tolerance = get_settings().beatport.match_bpm_tolerance
    return (
        min(
            abs(float(beatport_bpm) - float(audio_bpm)),
            abs(float(beatport_bpm) - 2.0 * float(audio_bpm)),
            abs(float(beatport_bpm) - 0.5 * float(audio_bpm)),
        )
        <= tolerance
    )


def canonical_mood_result(
    *,
    genre: str | None,
    sub_genre: str | None,
    bpm: float | None,
    energy_mean: float | None,
    audio_mood: str | None,
) -> CanonicalMood | None:
    """Map Beatport taxonomy to the internal 15-subgenre vocabulary.

    Beatport combines several styles in broad catalog buckets. For those
    buckets the audio classifier is retained only as a tie-breaker within the
    allowed Beatport family; BPM/energy provide a deterministic fallback.
    """
    genre_norm = (genre or "").strip().casefold()
    sub_norm = (sub_genre or "").strip().casefold()

    for hint, mood in _SUBGENRE_HINTS:
        if hint in sub_norm:
            return CanonicalMood(mood.value, 1.0)

    direct = _DIRECT_GENRE_MAP.get(genre_norm)
    if direct is not None:
        return CanonicalMood(direct.value, 0.95)

    if genre_norm == "techno (raw / deep / hypnotic)":
        allowed = {
            TechnoSubgenre.RAW.value,
            TechnoSubgenre.HYPNOTIC.value,
            TechnoSubgenre.DUB_TECHNO.value,
            TechnoSubgenre.AMBIENT_DUB.value,
        }
        if audio_mood in allowed:
            return CanonicalMood(audio_mood, 0.75)
        if energy_mean is not None and energy_mean < 0.38:
            return CanonicalMood(TechnoSubgenre.DUB_TECHNO.value, 0.65)
        if bpm is not None and bpm >= 137:
            return CanonicalMood(TechnoSubgenre.RAW.value, 0.65)
        return CanonicalMood(TechnoSubgenre.HYPNOTIC.value, 0.65)

    if genre_norm == "techno (peak time / driving)":
        allowed = {
            TechnoSubgenre.DRIVING.value,
            TechnoSubgenre.PEAK_TIME.value,
            TechnoSubgenre.INDUSTRIAL.value,
            TechnoSubgenre.HARD_TECHNO.value,
        }
        if audio_mood in allowed:
            return CanonicalMood(audio_mood, 0.75)
        if bpm is not None and bpm >= 145:
            return CanonicalMood(TechnoSubgenre.HARD_TECHNO.value, 0.65)
        if bpm is not None and bpm >= 134:
            return CanonicalMood(TechnoSubgenre.PEAK_TIME.value, 0.65)
        return CanonicalMood(TechnoSubgenre.DRIVING.value, 0.65)

    return None


def canonical_mood(
    *,
    genre: str | None,
    sub_genre: str | None,
    bpm: float | None,
    energy_mean: float | None,
    audio_mood: str | None,
) -> str | None:
    """Compatibility wrapper returning only the internal mood label."""
    result = canonical_mood_result(
        genre=genre,
        sub_genre=sub_genre,
        bpm=bpm,
        energy_mean=energy_mean,
        audio_mood=audio_mood,
    )
    return result.value if result is not None else None


def canonical_updates(
    match: dict[str, Any],
    *,
    current: Any | None,
    analysis_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build reversible feature updates from one Beatport match."""
    track = match.get("track") or {}
    features = analysis_features or {}
    confidence = match.get("confidence")
    beatport_bpm = match.get("bpm")
    camelot = match.get("camelot")
    beatport_key = match.get("key")
    genre = match.get("genre")
    sub_genre = match.get("sub_genre")

    audio_bpm = getattr(current, "audio_bpm", None)
    if audio_bpm is None:
        audio_bpm = features.get("bpm", getattr(current, "bpm", None))
    audio_bpm_confidence = getattr(current, "audio_bpm_confidence", None)
    if audio_bpm_confidence is None:
        audio_bpm_confidence = features.get(
            "bpm_confidence", getattr(current, "bpm_confidence", None)
        )
    audio_key_code = getattr(current, "audio_key_code", None)
    if audio_key_code is None:
        audio_key_code = features.get("key_code", getattr(current, "key_code", None))
    audio_key_confidence = getattr(current, "audio_key_confidence", None)
    if audio_key_confidence is None:
        audio_key_confidence = features.get(
            "key_confidence", getattr(current, "key_confidence", None)
        )
    audio_mood = getattr(current, "audio_mood", None)
    if audio_mood is None:
        audio_mood = features.get("mood", getattr(current, "mood", None))
    audio_mood_confidence = getattr(current, "audio_mood_confidence", None)
    if audio_mood_confidence is None:
        audio_mood_confidence = features.get(
            "mood_confidence", getattr(current, "mood_confidence", None)
        )

    values: dict[str, Any] = {
        "beatport_genre": genre,
        "beatport_sub_genre": sub_genre,
        "beatport_track_id": match.get("beatport_id"),
        "beatport_confidence": confidence,
        "beatport_bpm": beatport_bpm,
        "beatport_key": beatport_key,
        "beatport_camelot": camelot,
        "beatport_duration_ms": match.get("length_ms", track.get("length_ms")),
        "beatport_isrc": match.get("isrc", track.get("isrc")),
        "beatport_release": match.get("release", track.get("release")),
        "beatport_label": match.get("label", track.get("label")),
        "audio_bpm": audio_bpm,
        "audio_bpm_confidence": audio_bpm_confidence,
        "audio_key_code": audio_key_code,
        "audio_key_confidence": audio_key_confidence,
        "audio_mood": audio_mood,
        "audio_mood_confidence": audio_mood_confidence,
    }

    if confidence != "high":
        return values

    if beatport_bpm is not None and beatport_bpm_agrees(beatport_bpm, audio_bpm):
        values.update(bpm=float(beatport_bpm), bpm_confidence=1.0, bpm_source="beatport")
    key_code = beatport_key_code(camelot)
    if key_code is not None:
        values.update(key_code=key_code, key_confidence=1.0, key_source="beatport")

    mood = canonical_mood_result(
        genre=genre,
        sub_genre=sub_genre,
        bpm=float(beatport_bpm) if beatport_bpm is not None else audio_bpm,
        energy_mean=features.get("energy_mean", getattr(current, "energy_mean", None)),
        audio_mood=audio_mood,
    )
    if mood is not None:
        values.update(
            mood=mood.value,
            mood_confidence=mood.confidence,
            mood_source="beatport",
        )
    return values


def stored_genre_updates(current: Any | None) -> dict[str, Any]:
    """Promote an already-stored high-confidence Beatport genre."""
    if (
        current is None
        or getattr(current, "beatport_confidence", None) != "high"
        or getattr(current, "beatport_genre", None) is None
    ):
        return {}
    audio_mood = getattr(current, "audio_mood", None)
    if audio_mood is None and getattr(current, "mood_source", None) != "beatport":
        audio_mood = getattr(current, "mood", None)
    mood = canonical_mood_result(
        genre=current.beatport_genre,
        sub_genre=getattr(current, "beatport_sub_genre", None),
        bpm=getattr(current, "beatport_bpm", None) or getattr(current, "bpm", None),
        energy_mean=getattr(current, "energy_mean", None),
        audio_mood=audio_mood,
    )
    if mood is None:
        return {}
    return {
        "audio_mood": audio_mood,
        "audio_mood_confidence": (
            getattr(current, "audio_mood_confidence", None)
            if getattr(current, "audio_mood_confidence", None) is not None
            else getattr(current, "mood_confidence", None)
        ),
        "mood": mood.value,
        "mood_confidence": mood.confidence,
        "mood_source": "beatport",
    }
