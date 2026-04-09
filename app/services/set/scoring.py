"""Set scoring sub-service — score transitions between tracks and within sets."""

from __future__ import annotations

from typing import Any

from app.core.constants import SectionType
from app.core.errors import NotFoundError
from app.db.models.transition import Transition
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.transition import TransitionRepository
from app.services.mix_point_service import TrackSectionRow, build_section_context
from app.services.transition import TransitionScorer
from app.transition import SectionContext, TransitionScore, recommend_style, style_profile


class SetScoringService:
    """Score transitions for track pairs and full DJ sets."""

    def __init__(
        self,
        set_repo: SetRepository,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
    ) -> None:
        self._sets = set_repo
        self._features = feature_repo
        self._transitions = transition_repo

    @staticmethod
    def _coerce_section(section_id: int | None) -> SectionType | None:
        """Convert optional section id to SectionType enum, if valid."""
        if section_id is None:
            return None
        try:
            return SectionType(section_id)
        except ValueError:
            return None

    async def _load_section_rows(
        self,
        track_id: int,
        cache: dict[int, list[TrackSectionRow]],
    ) -> list[TrackSectionRow]:
        """Load and cache section rows for one track."""
        cached = cache.get(track_id)
        if cached is not None:
            return cached

        rows = await self._features.get_sections(track_id)
        converted: list[TrackSectionRow] = []
        for row in rows:
            section_type = self._coerce_section(row.section_type)
            if section_type is None:
                continue
            converted.append(
                TrackSectionRow(
                    section_type=section_type,
                    start_ms=row.start_ms,
                    end_ms=row.end_ms,
                )
            )
        cache[track_id] = converted
        return converted

    async def _resolve_section_context(
        self,
        from_item: Any,
        to_item: Any,
        section_rows_cache: dict[int, list[TrackSectionRow]],
    ) -> tuple[SectionContext | None, int | None, int | None, int | None]:
        """Resolve optional SectionContext for a set transition pair.

        Priority:
        1. Use explicit section ids from set items (out/in section ids).
        2. Fallback to mix-point based inference using track sections.
        3. If neither path has enough data, return no context.
        """
        from_section_id = getattr(from_item, "out_section_id", None)
        to_section_id = getattr(to_item, "in_section_id", None)
        from_section = self._coerce_section(from_section_id)
        to_section = self._coerce_section(to_section_id)

        if from_section is not None or to_section is not None:
            return (
                SectionContext(from_section=from_section, to_section=to_section),
                from_section_id if from_section is not None else None,
                to_section_id if to_section is not None else None,
                None,
            )

        mix_out_ms = getattr(from_item, "mix_out_point_ms", None)
        mix_in_ms = getattr(to_item, "mix_in_point_ms", None)
        if mix_out_ms is None and mix_in_ms is None:
            return None, None, None, None

        from_sections = await self._load_section_rows(from_item.track_id, section_rows_cache)
        to_sections = await self._load_section_rows(to_item.track_id, section_rows_cache)
        if not from_sections and not to_sections:
            return None, None, None, None

        ctx = build_section_context(
            from_sections=from_sections,
            from_mix_out_ms=mix_out_ms,
            to_sections=to_sections,
            to_mix_in_ms=mix_in_ms,
        )
        if ctx.from_section is None and ctx.to_section is None:
            return None, None, None, None

        return (
            ctx,
            int(ctx.from_section) if ctx.from_section is not None else None,
            int(ctx.to_section) if ctx.to_section is not None else None,
            None,
        )

    @staticmethod
    def _format_pair_response(
        from_id: int,
        to_id: int,
        *,
        overall: float | None,
        bpm: float | None,
        harmonic: float | None,
        energy: float | None,
        spectral: float | None,
        groove: float | None,
        timbral: float | None,
        hard_reject: bool | None,
        reject_reason: str | None,
        cached: bool,
    ) -> dict[str, Any]:
        """Build the canonical pair-score response envelope.

        All 6 components are surfaced, plus ``hard_reject`` /
        ``reject_reason`` so cache hits and fresh scores are
        indistinguishable to callers.
        """

        def _round(v: float | None) -> float | None:
            return round(v, 4) if v is not None else None

        # Reconstruct a TransitionScore from the persisted/computed
        # numbers so the style decision uses the SAME logic for cache
        # hits and fresh scores. Missing components default to 0 — they
        # only land in the response when the recommendation is genuine
        # (we hide style entirely when overall is None).
        recommended_style: str | None = None
        recommended_bars: float | int | None = None
        if overall is not None:
            synthetic = TransitionScore(
                bpm=bpm or 0.0,
                harmonic=harmonic or 0.0,
                energy=energy or 0.0,
                spectral=spectral or 0.0,
                groove=groove or 0.0,
                timbral=timbral or 0.0,
                overall=overall,
                hard_reject=bool(hard_reject) if hard_reject is not None else False,
                reject_reason=reject_reason,
            )
            style = recommend_style(synthetic)
            recommended_style = style.value
            profile_bars = style_profile(style)["bars"]
            recommended_bars = profile_bars if isinstance(profile_bars, int | float) else None

        return {
            "from_track_id": from_id,
            "to_track_id": to_id,
            "overall_quality": _round(overall),
            "bpm_score": _round(bpm),
            "harmonic_score": _round(harmonic),
            "energy_score": _round(energy),
            "spectral_score": _round(spectral),
            "groove_score": _round(groove),
            "timbral_score": _round(timbral),
            "hard_reject": bool(hard_reject) if hard_reject is not None else False,
            "reject_reason": reject_reason,
            "cached": cached,
            "recommended_style": recommended_style,
            "recommended_bars": recommended_bars,
        }

    async def score_pair(
        self,
        from_id: int,
        to_id: int,
        *,
        section_context: SectionContext | None = None,
        from_section_id: int | None = None,
        to_section_id: int | None = None,
        overlap_ms: int | None = None,
    ) -> dict[str, Any]:
        """Score transition between two tracks. Save to DB."""
        existing = await self._transitions.get_score(from_id, to_id)
        can_use_cache = (
            existing is not None
            and existing.overall_quality is not None
            and (
                (
                    section_context is None
                    and from_section_id is None
                    and to_section_id is None
                    and overlap_ms is None
                )
                or (
                    section_context is not None
                    and existing.from_section_id == from_section_id
                    and existing.to_section_id == to_section_id
                    and existing.overlap_ms == overlap_ms
                )
            )
        )
        if can_use_cache and existing is not None:
            return self._format_pair_response(
                from_id,
                to_id,
                overall=existing.overall_quality,
                bpm=existing.bpm_score,
                harmonic=existing.harmonic_score,
                energy=existing.energy_score,
                spectral=existing.spectral_score,
                groove=existing.groove_score,
                timbral=existing.timbral_score,
                hard_reject=existing.hard_reject,
                reject_reason=existing.reject_reason,
                cached=True,
            )

        ft_from = await self._features.get_scoring_features(from_id)
        ft_to = await self._features.get_scoring_features(to_id)

        if not ft_from or not ft_to:
            return {
                "from_track_id": from_id,
                "to_track_id": to_id,
                "overall_quality": None,
                "message": "Missing audio features for one or both tracks",
            }

        scorer = TransitionScorer()
        score = scorer.score(ft_from, ft_to, section_context=section_context)

        final_quality = 0.0 if score.hard_reject else score.overall

        transition = existing or Transition(from_track_id=from_id, to_track_id=to_id)
        transition.from_section_id = from_section_id
        transition.to_section_id = to_section_id
        transition.overlap_ms = overlap_ms
        transition.overall_quality = final_quality
        transition.bpm_score = score.bpm
        transition.harmonic_score = score.harmonic
        transition.energy_score = score.energy
        transition.spectral_score = score.spectral
        transition.groove_score = score.groove
        transition.timbral_score = score.timbral
        transition.hard_reject = score.hard_reject
        transition.reject_reason = score.reject_reason
        await self._transitions.save_score(transition)

        return self._format_pair_response(
            from_id,
            to_id,
            overall=final_quality,
            bpm=score.bpm,
            harmonic=score.harmonic,
            energy=score.energy,
            spectral=score.spectral,
            groove=score.groove,
            timbral=score.timbral,
            hard_reject=score.hard_reject,
            reject_reason=score.reject_reason,
            cached=False,
        )

    async def score_set_transitions(self, set_id: int) -> dict[str, Any]:
        """Score all sequential transitions in a set."""
        result = await self._sets.load_version_with_items(set_id)
        if result is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        latest, items = result

        section_rows_cache: dict[int, list[TrackSectionRow]] = {}
        transitions_data = []
        for i in range(len(items) - 1):
            from_item = items[i]
            to_item = items[i + 1]
            (
                section_context,
                from_section_id,
                to_section_id,
                overlap_ms,
            ) = await self._resolve_section_context(
                from_item,
                to_item,
                section_rows_cache,
            )
            score_data = await self.score_pair(
                from_item.track_id,
                to_item.track_id,
                section_context=section_context,
                from_section_id=from_section_id,
                to_section_id=to_section_id,
                overlap_ms=overlap_ms,
            )
            score_data["position"] = i
            score_data["used_section_context"] = section_context is not None
            score_data["from_section_id"] = from_section_id
            score_data["to_section_id"] = to_section_id
            transitions_data.append(score_data)

        scored = [t for t in transitions_data if t.get("overall_quality") is not None]
        hard_conflicts = [t for t in scored if t.get("hard_reject") is True]

        # Average only over non-reject, scored transitions.
        soft_scored = [t for t in scored if not t.get("hard_reject")]
        avg_score: float | None = None
        if soft_scored:
            avg_score = sum(float(t["overall_quality"]) for t in soft_scored) / len(soft_scored)

        return {
            "set_id": set_id,
            "version_id": latest.id,
            "total_transitions": len(transitions_data),
            "scored_transitions": len(scored),
            "hard_conflicts": len(hard_conflicts),
            "avg_score": avg_score,
            "transitions": transitions_data,
        }

    async def get_transition_candidates(self, track_id: int, top_n: int = 10) -> dict[str, Any]:
        """Get best transition candidates for a track. Stub — returns empty list."""
        return {
            "track_id": track_id,
            "candidates": [],
            "note": "Transition candidate search not yet implemented",
        }
