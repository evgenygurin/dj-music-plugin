"""Atomic audio tools — one operation per one track (tag: atomic, hidden by default).

Unlock via: unlock_tools(action="unlock", category="atomic")
Composites (analyze_batch, classify_mood, gate_by_audio) call these internally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from sqlalchemy import select

from app.audio.mood import MoodClassifier
from app.audio.pipeline import AnalysisPipeline
from app.audio.registry import AnalyzerRegistry
from app.config import settings
from app.mcp.dependencies import get_analyzer_registry, get_db_session, get_ym_client
from app.models.audio import TrackAudioFeaturesComputed
from app.models.library import DjLibraryItem
from app.models.track import Track
from app.server import mcp
from app.ym.client import YandexMusicClient

# ── 1. analyze_one_track ──────────────────────────


@mcp.tool(tags={"atomic"}, annotations={"readOnlyHint": False}, timeout=180.0)
async def analyze_one_track(
    track_id: int,
    analyzers: list[str] | None = None,
    force: bool = False,
    registry: AnalyzerRegistry = Depends(get_analyzer_registry),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis pipeline on ONE track. Saves features to DB."""
    async with get_db_session() as session:
        track = (
            await session.execute(select(Track).where(Track.id == track_id))
        ).scalar_one_or_none()
        if not track:
            raise ToolError(f"Track {track_id} not found")

        # Check cached
        if not force:
            existing = (
                await session.execute(
                    select(TrackAudioFeaturesComputed).where(
                        TrackAudioFeaturesComputed.track_id == track_id
                    )
                )
            ).scalar_one_or_none()
            if existing:
                return {"track_id": track_id, "status": "cached", "has_features": True}

        # Find audio file
        lib_item = (
            await session.execute(select(DjLibraryItem).where(DjLibraryItem.track_id == track_id))
        ).scalar_one_or_none()

        if not lib_item or not lib_item.file_path:
            raise ToolError(f"No audio file for track {track_id}")

        file_path = Path(lib_item.file_path)
        if not file_path.exists():
            raise ToolError(f"Audio file not found: {file_path}")

        # Check iCloud stub
        stat = file_path.stat()
        if hasattr(stat, "st_blocks") and stat.st_blocks * 512 < stat.st_size * 0.9:
            raise ToolError(f"iCloud stub (not downloaded): {file_path.name}")

    # Run pipeline
    pipeline = AnalysisPipeline(registry)
    result = await pipeline.analyze(str(file_path), analyzers=analyzers)

    # Save to DB
    async with get_db_session() as session:
        from app.models.audio import FeatureExtractionRun

        run = FeatureExtractionRun(
            track_id=track_id,
            pipeline_name="mcp_analyze",
            pipeline_version="1.0",
            status="completed",
        )
        session.add(run)
        await session.flush()

        features = TrackAudioFeaturesComputed(
            track_id=track_id,
            pipeline_run_id=run.id,
            **result.features,
        )
        session.add(features)

    return {
        "track_id": track_id,
        "status": "analyzed",
        "analyzers_run": result.analyzers_run if hasattr(result, "analyzers_run") else [],
        "errors": result.errors if hasattr(result, "errors") else [],
        "feature_count": len(result.features) if hasattr(result, "features") else 0,
    }


# ── 2. classify_one_track ─────────────────────────


@mcp.tool(tags={"atomic"}, annotations={"readOnlyHint": False})
async def classify_one_track(
    track_id: int,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Classify ONE track mood/subgenre and SAVE to DB."""
    async with get_db_session() as session:
        features = (
            await session.execute(
                select(TrackAudioFeaturesComputed).where(
                    TrackAudioFeaturesComputed.track_id == track_id
                )
            )
        ).scalar_one_or_none()

        if not features:
            raise ToolError(
                f"No audio features for track {track_id}. Run analyze_one_track first."
            )

        # Build features dict for classifier
        feat_dict = {
            "bpm": features.bpm,
            "integrated_lufs": features.integrated_lufs,
            "energy_mean": features.energy_mean,
            "energy_max": features.energy_max,
            "energy_std": features.energy_std,
            "energy_slope": features.energy_slope,
            "spectral_centroid_hz": features.spectral_centroid_hz,
            "spectral_flatness": features.spectral_flatness,
            "spectral_flux_mean": features.spectral_flux_mean,
            "spectral_flux_std": features.spectral_flux_std,
            "loudness_range_lu": features.loudness_range_lu,
            "crest_factor_db": features.crest_factor_db,
            "hp_ratio": features.hp_ratio,
            "onset_rate": features.onset_rate,
            "pulse_clarity": features.pulse_clarity,
            "kick_prominence": features.kick_prominence,
            "hnr_db": features.hnr_db,
        }

        classifier = MoodClassifier()
        result = classifier.classify(feat_dict)

        # Persist mood
        features.mood = result.mood.value
        features.mood_confidence = result.confidence

        return {
            "track_id": track_id,
            "mood": result.mood.value,
            "confidence": round(result.confidence, 3),
            "reasoning": result.reasoning,
            "top_3": [
                {"subgenre": sg.value, "score": round(sc, 3)}
                for sg, sc in sorted(result.scores.items(), key=lambda x: x[1], reverse=True)[:3]
            ],
        }


# ── 3. gate_one_track ─────────────────────────────


@mcp.tool(tags={"atomic"}, annotations={"readOnlyHint": True})
async def gate_one_track(
    track_id: int,
    criteria: dict[str, float] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Check ONE track against audio quality criteria. Returns pass/fail + reasons."""
    async with get_db_session() as session:
        features = (
            await session.execute(
                select(TrackAudioFeaturesComputed).where(
                    TrackAudioFeaturesComputed.track_id == track_id
                )
            )
        ).scalar_one_or_none()

        if not features:
            return {"track_id": track_id, "passed": None, "reasons": ["no_features"]}

    # Build criteria from defaults + overrides
    reasons: list[str] = []

    def _check(name: str, value: float | None, op: str, threshold: float) -> None:
        if value is None:
            return
        if op == ">=" and value < threshold:
            reasons.append(f"{name}={value:.2f} (<{threshold})")
        elif op == "<=" and value > threshold:
            reasons.append(f"{name}={value:.2f} (>{threshold})")

    c = criteria or {}
    _check("bpm", features.bpm, ">=", c.get("bpm_min", settings.techno_bpm_min))
    _check("bpm", features.bpm, "<=", c.get("bpm_max", settings.techno_bpm_max))
    _check("lufs", features.integrated_lufs, ">=", c.get("lufs_min", settings.techno_lufs_min))
    _check("lufs", features.integrated_lufs, "<=", c.get("lufs_max", settings.techno_lufs_max))
    _check("energy", features.energy_mean, ">=", c.get("energy_min", settings.techno_energy_min))
    _check(
        "onset_rate",
        features.onset_rate,
        ">=",
        c.get("onset_rate_min", settings.techno_onset_rate_min),
    )
    _check(
        "kick",
        features.kick_prominence,
        ">=",
        c.get("kick_min", settings.techno_kick_prominence_min),
    )
    _check(
        "centroid",
        features.spectral_centroid_hz,
        ">=",
        c.get("centroid_min", settings.techno_centroid_min),
    )
    _check(
        "centroid",
        features.spectral_centroid_hz,
        "<=",
        c.get("centroid_max", settings.techno_centroid_max),
    )
    _check(
        "flatness",
        features.spectral_flatness,
        "<=",
        c.get("flatness_max", settings.techno_flatness_max),
    )
    _check(
        "hp_ratio", features.hp_ratio, "<=", c.get("hp_ratio_max", settings.techno_hp_ratio_max)
    )
    _check(
        "crest",
        features.crest_factor_db,
        "<=",
        c.get("crest_max", settings.techno_crest_factor_max),
    )
    _check("lra", features.loudness_range_lu, "<=", c.get("lra_max", settings.techno_lra_max))
    _check("hnr", features.hnr_db, ">=", c.get("hnr_min", settings.techno_hnr_min))
    _check(
        "tempo_conf",
        features.bpm_confidence,
        ">=",
        c.get("tempo_conf_min", settings.techno_tempo_confidence_min),
    )
    _check(
        "bpm_stab",
        features.bpm_stability,
        ">=",
        c.get("bpm_stab_min", settings.techno_bpm_stability_min),
    )
    _check(
        "pulse",
        features.pulse_clarity,
        ">=",
        c.get("pulse_min", settings.techno_pulse_clarity_min),
    )

    return {
        "track_id": track_id,
        "passed": len(reasons) == 0,
        "reasons": reasons,
    }


# ── 4. get_similar_one_track ──────────────────────


@mcp.tool(tags={"atomic"}, annotations={"readOnlyHint": True, "openWorldHint": True})
async def get_similar_one_track(
    ym_track_id: str,
    limit: int = 20,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    genre_filter: list[str] | None = None,
    genre_blacklist: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get similar tracks from YM for ONE track ID. Raw YM API with filters."""
    from app.mcp.tools.discovery import _genre_ok, _is_excluded, _ym_track_dict

    raw_similar = await ym.get_similar(ym_track_id)

    min_dur = min_duration_ms or settings.discovery_min_duration_ms
    max_dur = max_duration_ms or settings.discovery_max_duration_ms

    filtered = []
    for t in raw_similar:
        dur = t.duration_ms or 0
        if dur and (dur < min_dur or dur > max_dur):
            continue
        if _is_excluded(t.title, exclude_patterns):
            continue
        if not _genre_ok(t.albums or [], whitelist=genre_filter, blacklist=genre_blacklist):
            continue
        filtered.append(_ym_track_dict(t))
        if len(filtered) >= limit:
            break

    return {
        "ym_track_id": ym_track_id,
        "total_raw": len(raw_similar),
        "after_filter": len(filtered),
        "similar": filtered,
    }
