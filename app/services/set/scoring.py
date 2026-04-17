"""Set scoring sub-service — score transitions between tracks and within sets."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import String, case, func, select
from sqlalchemy.orm import aliased

from app.camelot.wheel import camelot_distance, key_code_to_camelot
from app.core.constants import SectionType
from app.core.errors import NotFoundError, ValidationError
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track
from app.db.models.transition import Transition
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.transition import TransitionRepository
from app.services.mix_point_service import TrackSectionRow, build_section_context
from app.transition import (
    SectionContext,
    TransitionRecommendation,
    TransitionScore,
)
from app.transition.recommender import TransitionRecommender


def _safe_parse_recommendation(raw: str | None) -> TransitionRecommendation | None:
    if not raw:
        return None
    try:
        return TransitionRecommendation.model_validate_json(raw)
    except Exception:
        return None


from app.transition.math_helpers import bpm_distance
from app.transition.scorer import TransitionScorer

_TRANSITION_FILTER_OPERATORS: frozenset[str] = frozenset(
    {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "is_null"}
)

_INCLUDE_MACRO_ALL = "all"
_INCLUDE_MACRO_ALL_TRANSITION = "all_transition_fields"
_INCLUDE_MACRO_ALL_TRACK = "all_track_fields"
_INCLUDE_MACRO_ALL_FEATURE = "all_feature_fields"
_INCLUDE_MACRO_TRANSITION = "transition_fields"
_INCLUDE_MACRO_TRACK = "track_fields"
_INCLUDE_MACRO_FEATURE = "feature_fields"
_MAX_SUBSET_TRACKS = 300


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
    def _to_jsonable(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime | date):
            return value.isoformat()
        return value

    @staticmethod
    def _normalize_field_list(raw: list[str] | None) -> list[str] | None:
        if raw is None:
            return None
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            name = str(item).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
        return out

    @staticmethod
    def _expand_field_macros(
        requested_fields: list[str] | None,
        macro_map: dict[str, list[str]],
    ) -> list[str] | None:
        """Expand include/exclude macro tokens into concrete field names."""
        if requested_fields is None:
            return None

        out: list[str] = []
        seen: set[str] = set()
        for token in requested_fields:
            names = macro_map.get(token)
            if names is None:
                names = [token]
            for name in names:
                if name in seen:
                    continue
                seen.add(name)
                out.append(name)
        return out

    @staticmethod
    def _parse_sort_spec(sort_by: str, fallback_order: str) -> list[tuple[str, str]]:
        tokens = [chunk.strip() for chunk in sort_by.split(",") if chunk.strip()]
        if not tokens:
            raise ValidationError("sort_by cannot be empty")

        fallback = fallback_order.lower()
        if fallback not in {"asc", "desc"}:
            raise ValidationError("sort_order must be 'asc' or 'desc'")

        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for token in tokens:
            direction = fallback
            field = token
            if token.startswith("-"):
                direction = "desc"
                field = token[1:].strip()
            elif token.startswith("+"):
                direction = "asc"
                field = token[1:].strip()

            if not field:
                raise ValidationError(f"Invalid sort token: {token!r}")
            if field in seen:
                continue
            seen.add(field)
            out.append((field, direction))
        return out

    @staticmethod
    def _build_filter_clauses(
        filters: dict[str, Any],
        field_map: dict[str, Any],
    ) -> list[Any]:
        clauses: list[Any] = []

        for field_name, raw_filter in filters.items():
            column = field_map.get(field_name)
            if column is None:
                raise ValidationError(f"Unknown filter field: {field_name}")

            if isinstance(raw_filter, dict):
                if not raw_filter:
                    continue
                for op, value in raw_filter.items():
                    op_norm = str(op).strip().lower()
                    if op_norm not in _TRANSITION_FILTER_OPERATORS:
                        raise ValidationError(
                            f"Unknown operator {op!r} for field {field_name}. "
                            f"Allowed: {sorted(_TRANSITION_FILTER_OPERATORS)}"
                        )
                    if op_norm == "eq":
                        clauses.append(column == value)
                    elif op_norm == "ne":
                        clauses.append(column != value)
                    elif op_norm == "gt":
                        clauses.append(column > value)
                    elif op_norm == "gte":
                        clauses.append(column >= value)
                    elif op_norm == "lt":
                        clauses.append(column < value)
                    elif op_norm == "lte":
                        clauses.append(column <= value)
                    elif op_norm == "in":
                        if not isinstance(value, list | tuple | set):
                            raise ValidationError(f"{field_name}.in must be list/tuple/set")
                        seq = list(value)
                        if not seq:
                            raise ValidationError(f"{field_name}.in cannot be empty")
                        clauses.append(column.in_(seq))
                    elif op_norm == "not_in":
                        if not isinstance(value, list | tuple | set):
                            raise ValidationError(f"{field_name}.not_in must be list/tuple/set")
                        seq = list(value)
                        if not seq:
                            raise ValidationError(f"{field_name}.not_in cannot be empty")
                        clauses.append(~column.in_(seq))
                    elif op_norm == "contains":
                        if value is None:
                            raise ValidationError(
                                f"{field_name}.contains requires a non-null value"
                            )
                        clauses.append(func.cast(column, String).ilike(f"%{value}%"))
                    elif op_norm == "is_null":
                        if not isinstance(value, bool):
                            raise ValidationError(f"{field_name}.is_null must be boolean")
                        clauses.append(column.is_(None) if value else column.is_not(None))
            else:
                clauses.append(column == raw_filter)

        return clauses

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
        persisted_recipe_json: str | None = None,
    ) -> dict[str, Any]:
        """Build the canonical pair-score response envelope.

        All 6 components are surfaced, plus ``hard_reject`` /
        ``reject_reason`` so cache hits and fresh scores are
        indistinguishable to callers. Neural Mix FX is a single ``fx_type``
        string (not duplicated under legacy aliases).
        """

        def _round(v: float | None) -> float | None:
            return round(v, 4) if v is not None else None

        fx_type: str | None = None
        transition_bars: int | None = None
        recipe_confidence: float | None = None
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
            from app.entities.audio.features import TrackFeatures as _TrackFeatures

            empty = _TrackFeatures()
            persisted = _safe_parse_recommendation(persisted_recipe_json)
            rec = persisted or TransitionRecommender().recommend(synthetic, empty, empty)
            fx_type = rec.fx_type.value
            transition_bars = None
            recipe_confidence = rec.confidence

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
            "fx_type": fx_type,
            "transition_bars": transition_bars if overall is not None else None,
            "recipe_confidence": recipe_confidence if overall is not None else None,
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
        features_cache: dict[int, Any] | None = None,
        existing_cache: dict[tuple[int, int], Transition] | None = None,
    ) -> dict[str, Any]:
        """Score transition between two tracks. Save to DB.

        When invoked inside a bulk loop (see :meth:`score_set_transitions`),
        the caller can pass ``features_cache`` and ``existing_cache`` to
        avoid hitting the database once per pair: both maps are pre-loaded
        via a single batch query upstream, so the hot loop makes zero extra
        round-trips.
        """
        if existing_cache is not None:
            existing = existing_cache.get((from_id, to_id))
        else:
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
                persisted_recipe_json=existing.transition_recipe_json,
            )

        if features_cache is not None:
            ft_from = features_cache.get(from_id)
            ft_to = features_cache.get(to_id)
        else:
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

        # Apply transition history bonus (Phase 1 AI intelligence)
        try:
            from app.db.repositories.transition_history import TransitionHistoryRepository
            from app.services.transition_history import TransitionHistoryService

            history_svc = TransitionHistoryService(
                TransitionHistoryRepository(self._transitions.session)
            )
            final_quality = await history_svc.apply_history_bonus(from_id, to_id, final_quality)
        except Exception:
            pass  # History bonus is non-critical; scoring works without it

        # Recommend Neural Mix FX with real features
        recipe = TransitionRecommender().recommend(
            score, ft_from, ft_to, section_context=section_context
        )

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
        transition.fx_type = recipe.fx_type.value
        transition.transition_bars = None
        transition.transition_recipe_json = recipe.model_dump_json()
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
            persisted_recipe_json=recipe.model_dump_json(),
        )

    async def score_set_transitions(self, set_id: int) -> dict[str, Any]:
        """Score all sequential transitions in a set.

        Optimised vs. the previous naive implementation:

        * **Single batch-fetch** loads features for every track in the set
          instead of N individual ``get_scoring_features`` calls — one SQL
          round-trip instead of 2*N (once per pair endpoint).
        * **Single batch-fetch** of existing transition rows short-circuits
          already-scored pairs without N separate ``get_score`` queries.
        * Per-pair recipe generation still runs because each pair can have
          different section contexts, but the DB cost drops from O(N) to O(1).
        """
        result = await self._sets.load_version_with_items(set_id)
        if result is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        latest, items = result

        # Pre-batch the DB loads so the inner loop never waits on I/O.
        involved_ids = list({item.track_id for item in items})
        features_cache = await self._features.get_scoring_features_batch(involved_ids)

        pair_keys = [(items[i].track_id, items[i + 1].track_id) for i in range(len(items) - 1)]
        existing_cache = await self._transitions.get_scores_batch(pair_keys)

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
                features_cache=features_cache,
                existing_cache=existing_cache,
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

    async def score_subset_transitions(
        self,
        track_ids: list[int],
        *,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """Score all directed pairs within an explicit subset of tracks.

        Use this to avoid all-library all-vs-all scoring: prefilter tracks first,
        then evaluate only the remaining candidate pool.
        """
        if top_n < 1:
            raise ValidationError("top_n must be >= 1")

        unique_ids: list[int] = []
        seen: set[int] = set()
        for tid in track_ids:
            if tid in seen:
                continue
            seen.add(tid)
            unique_ids.append(tid)

        if len(unique_ids) < 2:
            raise ValidationError("subset mode requires at least 2 unique track_ids")
        if len(unique_ids) > _MAX_SUBSET_TRACKS:
            raise ValidationError(
                f"subset mode supports up to {_MAX_SUBSET_TRACKS} unique track_ids"
            )

        pair_keys = [
            (from_id, to_id)
            for from_id in unique_ids
            for to_id in unique_ids
            if from_id != to_id
        ]
        features_cache = await self._features.get_scoring_features_batch(unique_ids)
        existing_cache = await self._transitions.get_scores_batch(pair_keys)

        transitions_data: list[dict[str, Any]] = []
        for from_id, to_id in pair_keys:
            score_data = await self.score_pair(
                from_id,
                to_id,
                features_cache=features_cache,
                existing_cache=existing_cache,
            )
            transitions_data.append(score_data)

        scored = [t for t in transitions_data if t.get("overall_quality") is not None]
        hard_conflicts = [t for t in scored if t.get("hard_reject") is True]
        soft_scored = [t for t in scored if not t.get("hard_reject")]
        avg_score: float | None = None
        if soft_scored:
            avg_score = sum(float(t["overall_quality"]) for t in soft_scored) / len(soft_scored)

        ranked = sorted(
            scored,
            key=lambda row: float(row.get("overall_quality") or 0.0),
            reverse=True,
        )
        top_transitions = ranked[:top_n]

        return {
            "mode": "subset",
            "input_track_count": len(track_ids),
            "track_count": len(unique_ids),
            "track_ids": unique_ids,
            "total_pairs": len(pair_keys),
            "scored_pairs": len(scored),
            "hard_conflicts": len(hard_conflicts),
            "avg_score": avg_score,
            "top_n": top_n,
            "top_transitions": top_transitions,
            "transitions": transitions_data,
        }

    async def search_transitions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "-overall_quality",
        sort_order: str = "desc",
        sort_direction: str | None = None,
        filters: dict[str, Any] | None = None,
        include_fields: list[str] | None = None,
        exclude_fields: list[str] | None = None,
        include_stats: bool = True,
        include_field_catalog: bool = False,
        target_quality: float | None = None,
    ) -> dict[str, Any]:
        """Search scored transition pairs with flexible filtering/sorting/projection.

        Supports:
        - pagination via ``limit``/``offset``
        - multi-sort via comma-separated ``sort_by`` (``-field`` => desc; use ``+field`` for asc)
        - per-field operators via ``filters`` dict
        - field projection via ``include_fields`` / ``exclude_fields`` (default rows: ``id`` only)
        - aggregate stats for the filtered set
        - optional heavy field-name catalog (``include_field_catalog``) for MCP payload control
        - optional target feasibility guardrail via ``target_quality`` (0..1)
        """
        if limit < 1:
            raise ValidationError("limit must be >= 1")
        if offset < 0:
            raise ValidationError("offset must be >= 0")

        normalized_filters = filters or {}
        if not isinstance(normalized_filters, dict):
            raise ValidationError("filters must be an object/dict")

        from_track = aliased(Track, name="from_track")
        to_track = aliased(Track, name="to_track")
        from_features = aliased(TrackAudioFeaturesComputed, name="from_features")
        to_features = aliased(TrackAudioFeaturesComputed, name="to_features")

        transition_fields = [col.name for col in Transition.__table__.columns]
        track_fields: list[str] = []
        feature_fields: list[str] = []

        field_map: dict[str, Any] = {
            col.name: getattr(Transition, col.name) for col in Transition.__table__.columns
        }

        for col in Track.__table__.columns:
            from_col = getattr(from_track, col.name)
            to_col = getattr(to_track, col.name)
            from_field = f"from_track_{col.name}"
            to_field = f"to_track_{col.name}"
            field_map[from_field] = from_col
            field_map[to_field] = to_col
            track_fields.extend([from_field, to_field])
            if col.name in {"title", "sort_title", "duration_ms", "status"}:
                field_map[f"from_{col.name}"] = from_col
                field_map[f"to_{col.name}"] = to_col

        for col in TrackAudioFeaturesComputed.__table__.columns:
            if col.name == "track_id":
                # Preserve transition.from_track_id/to_track_id names and expose
                # feature FK columns explicitly to still cover "all feature fields".
                from_field = "from_feature_track_id"
                to_field = "to_feature_track_id"
            else:
                from_field = f"from_{col.name}"
                to_field = f"to_{col.name}"
            field_map[from_field] = getattr(from_features, col.name)
            field_map[to_field] = getattr(to_features, col.name)
            feature_fields.extend([from_field, to_field])

        available_fields = sorted(field_map.keys())
        macro_map = {
            _INCLUDE_MACRO_ALL: available_fields,
            _INCLUDE_MACRO_ALL_TRANSITION: transition_fields,
            _INCLUDE_MACRO_TRANSITION: transition_fields,
            _INCLUDE_MACRO_ALL_TRACK: sorted(track_fields),
            _INCLUDE_MACRO_TRACK: sorted(track_fields),
            _INCLUDE_MACRO_ALL_FEATURE: sorted(feature_fields),
            _INCLUDE_MACRO_FEATURE: sorted(feature_fields),
        }

        include = self._normalize_field_list(include_fields)
        exclude = self._normalize_field_list(exclude_fields) or []
        include = self._expand_field_macros(include, macro_map)
        exclude = self._expand_field_macros(exclude, macro_map) or []

        # Default = minimal projection (id only) to keep MCP payloads small; expand via macros / list.
        selected_fields = ["id"] if include is None else include

        unknown_include = [name for name in selected_fields if name not in field_map]
        if unknown_include:
            raise ValidationError(f"Unknown include_fields: {unknown_include}")

        unknown_exclude = [name for name in exclude if name not in field_map]
        if unknown_exclude:
            raise ValidationError(f"Unknown exclude_fields: {unknown_exclude}")

        exclude_set = set(exclude)
        selected_fields = [name for name in selected_fields if name not in exclude_set]
        if not selected_fields:
            raise ValidationError("No output fields left after include/exclude filtering")

        effective_sort_direction = (sort_direction or sort_order).lower()
        sort_spec = self._parse_sort_spec(sort_by, effective_sort_direction)
        for field_name, _direction in sort_spec:
            if field_name not in field_map:
                raise ValidationError(f"Unknown sort field: {field_name}")
        if not any(field_name == "id" for field_name, _direction in sort_spec):
            sort_spec.append(("id", effective_sort_direction))

        where_clauses = self._build_filter_clauses(normalized_filters, field_map)

        def _base_select(*cols: Any) -> Any:
            stmt = (
                select(*cols)
                .select_from(Transition)
                .join(from_track, Transition.from_track_id == from_track.id)
                .join(to_track, Transition.to_track_id == to_track.id)
                .outerjoin(from_features, from_features.track_id == Transition.from_track_id)
                .outerjoin(to_features, to_features.track_id == Transition.to_track_id)
            )
            if where_clauses:
                stmt = stmt.where(*where_clauses)
            return stmt

        count_stmt = select(func.count()).select_from(_base_select(Transition.id).subquery())
        total = int((await self._transitions.session.execute(count_stmt)).scalar_one() or 0)

        select_cols = [field_map[name].label(name) for name in selected_fields]
        rows_stmt = _base_select(*select_cols)
        for field_name, direction in sort_spec:
            sort_col = field_map[field_name]
            if direction == "desc":
                rows_stmt = rows_stmt.order_by(sort_col.desc().nullslast())
            else:
                rows_stmt = rows_stmt.order_by(sort_col.asc().nullslast())
        rows_stmt = rows_stmt.offset(offset).limit(limit)

        raw_rows = (await self._transitions.session.execute(rows_stmt)).mappings().all()
        rows = [
            {key: self._to_jsonable(value) for key, value in dict(row).items()} for row in raw_rows
        ]

        stats: dict[str, Any] | None = None
        quality_guardrail: dict[str, Any] | None = None
        if include_stats:
            stats_subq = _base_select(
                Transition.hard_reject.label("hard_reject"),
                Transition.overall_quality.label("overall_quality"),
                Transition.bpm_score.label("bpm_score"),
                Transition.harmonic_score.label("harmonic_score"),
                Transition.energy_score.label("energy_score"),
                Transition.spectral_score.label("spectral_score"),
                Transition.groove_score.label("groove_score"),
                Transition.timbral_score.label("timbral_score"),
                Transition.fx_type.label("fx_type"),
            ).subquery("transition_stats")

            stats_stmt = select(
                func.count().label("total_rows"),
                func.sum(case((stats_subq.c.hard_reject.is_(True), 1), else_=0)).label(
                    "hard_reject_count"
                ),
                func.avg(stats_subq.c.overall_quality).label("overall_avg"),
                func.min(stats_subq.c.overall_quality).label("overall_min"),
                func.max(stats_subq.c.overall_quality).label("overall_max"),
                func.avg(stats_subq.c.bpm_score).label("bpm_avg"),
                func.avg(stats_subq.c.harmonic_score).label("harmonic_avg"),
                func.avg(stats_subq.c.energy_score).label("energy_avg"),
                func.avg(stats_subq.c.spectral_score).label("spectral_avg"),
                func.avg(stats_subq.c.groove_score).label("groove_avg"),
                func.avg(stats_subq.c.timbral_score).label("timbral_avg"),
            )
            stats_row = (await self._transitions.session.execute(stats_stmt)).mappings().one()

            hard_reject_count = int(stats_row["hard_reject_count"] or 0)
            total_rows = int(stats_row["total_rows"] or 0)

            fx_stmt = (
                select(
                    stats_subq.c.fx_type.label("fx_type"),
                    func.count().label("count"),
                )
                .where(stats_subq.c.fx_type.is_not(None))
                .group_by(stats_subq.c.fx_type)
                .order_by(func.count().desc(), stats_subq.c.fx_type.asc())
                .limit(10)
            )
            fx_rows = (await self._transitions.session.execute(fx_stmt)).mappings().all()

            stats = {
                "total_rows": total_rows,
                "hard_reject_count": hard_reject_count,
                "hard_reject_ratio": round(hard_reject_count / total_rows, 4)
                if total_rows
                else None,
                "overall_quality": {
                    "avg": self._to_jsonable(stats_row["overall_avg"]),
                    "min": self._to_jsonable(stats_row["overall_min"]),
                    "max": self._to_jsonable(stats_row["overall_max"]),
                },
                "component_averages": {
                    "bpm": self._to_jsonable(stats_row["bpm_avg"]),
                    "harmonic": self._to_jsonable(stats_row["harmonic_avg"]),
                    "energy": self._to_jsonable(stats_row["energy_avg"]),
                    "spectral": self._to_jsonable(stats_row["spectral_avg"]),
                    "groove": self._to_jsonable(stats_row["groove_avg"]),
                    "timbral": self._to_jsonable(stats_row["timbral_avg"]),
                },
                "fx_type_top": [
                    {"fx_type": row["fx_type"], "count": int(row["count"])} for row in fx_rows
                ],
            }

            max_overall_raw = stats_row["overall_max"]
            max_overall = self._to_jsonable(max_overall_raw)
            if target_quality is None:
                quality_guardrail = {
                    "target_quality": None,
                    "max_overall_quality": max_overall,
                    "meets_target": None,
                    "non_reject_rows_at_or_above_target": None,
                    "message": (
                        "Pass target_quality to get explicit feasibility for your desired threshold."
                    ),
                }
            else:
                meets_target = (
                    bool(max_overall_raw is not None and float(max_overall_raw) >= target_quality)
                    if max_overall_raw is not None
                    else False
                )
                count_at_target_stmt = select(func.count()).select_from(stats_subq).where(
                    stats_subq.c.hard_reject.is_(False),
                    stats_subq.c.overall_quality.is_not(None),
                    stats_subq.c.overall_quality >= target_quality,
                )
                rows_at_target = int(
                    (await self._transitions.session.execute(count_at_target_stmt)).scalar_one() or 0
                )
                if meets_target:
                    message = (
                        "Target quality is feasible in the current filtered slice. "
                        "Use these rows to build your path/set."
                    )
                else:
                    message = (
                        "Target quality exceeds current transition ceiling. "
                        "Lower target, widen filters, or refresh transition scoring."
                    )
                quality_guardrail = {
                    "target_quality": target_quality,
                    "max_overall_quality": max_overall,
                    "meets_target": meets_target,
                    "non_reject_rows_at_or_above_target": rows_at_target,
                    "message": message,
                }

        next_offset = offset + len(rows)
        fields_payload: dict[str, Any] = {
            "selected": selected_fields,
            "excluded": exclude,
        }
        if include_field_catalog:
            fields_payload["available"] = available_fields
            fields_payload["groups"] = {
                "transition_fields": transition_fields,
                "track_fields": sorted(track_fields),
                "feature_fields": sorted(feature_fields),
            }
            fields_payload["include_macros"] = sorted(macro_map.keys())

        out: dict[str, Any] = {
            "rows": rows,
            "offset": offset,
            "limit": limit,
            "returned": len(rows),
            "total": total,
            "next_offset": next_offset if next_offset < total else None,
            "truncated": next_offset < total,
            "sort": [
                {"field": field_name, "direction": direction}
                for field_name, direction in sort_spec
            ],
            "filters_applied": normalized_filters,
            "fields": fields_payload,
            "stats": stats,
            "quality_guardrail": quality_guardrail,
        }
        if include_field_catalog:
            out["filter_operators"] = sorted(_TRANSITION_FILTER_OPERATORS)
        return out

    async def get_transition_candidates(self, track_id: int, top_n: int = 10) -> dict[str, Any]:
        """Get best transition candidates for a track across the analyzed library.

        The panel's "recommended next" and set-mode picker expect the backend
        to search broadly first, then rank by the full TransitionScorer. This
        method therefore scores the current track against every analyzed track
        in the library (excluding itself), drops hard rejects, and returns the
        strongest matches with a few explanatory fields for the UI.
        """
        current = await self._features.get_scoring_features(track_id)
        if current is None or current.bpm is None:
            return {
                "track_id": track_id,
                "candidates": [],
                "pool_size": 0,
                "scored": 0,
                "note": "Current track has no audio features — analyze first",
            }

        pool_ids = await self._features.get_all_track_ids_with_features()
        pool_ids = [tid for tid in pool_ids if tid != track_id]
        if not pool_ids:
            return {
                "track_id": track_id,
                "candidates": [],
                "pool_size": 0,
                "scored": 0,
                "note": "No analyzed tracks available in the library",
            }

        features_map = await self._features.get_scoring_features_batch(pool_ids)
        scorer = TransitionScorer()
        candidates: list[dict[str, Any]] = []

        for candidate_id, candidate in features_map.items():
            if candidate.bpm is None:
                continue

            score = scorer.score(current, candidate)
            if score.hard_reject:
                continue

            candidate_bpm_distance = (
                bpm_distance(current.bpm, candidate.bpm)
                if current.bpm is not None and candidate.bpm is not None
                else None
            )
            candidate_key_distance = (
                camelot_distance(current.key_code, candidate.key_code)
                if current.key_code is not None and candidate.key_code is not None
                else None
            )
            energy_step = (
                candidate.integrated_lufs - current.integrated_lufs
                if current.integrated_lufs is not None and candidate.integrated_lufs is not None
                else None
            )

            candidates.append(
                {
                    "to_track_id": candidate_id,
                    "overall_quality": round(score.overall, 4),
                    "bpm_distance": round(candidate_bpm_distance, 4)
                    if candidate_bpm_distance is not None
                    else None,
                    "energy_step": round(energy_step, 4) if energy_step is not None else None,
                    "energy_delta": round(abs(energy_step), 4)
                    if energy_step is not None
                    else None,
                    "groove_similarity": round(score.groove, 4),
                    "harmonic_score": round(score.harmonic, 4),
                    "key_distance": candidate_key_distance,
                    "key_distance_weighted": round(score.harmonic, 4),
                    "camelot": key_code_to_camelot(candidate.key_code)
                    if candidate.key_code is not None
                    else None,
                    "bpm": candidate.bpm,
                    "mood": candidate.mood,
                    "lufs": candidate.integrated_lufs,
                }
            )

        candidates.sort(
            key=lambda candidate: (
                -float(candidate["overall_quality"]),
                float(candidate["bpm_distance"])
                if candidate["bpm_distance"] is not None
                else float("inf"),
                int(candidate["key_distance"]) if candidate["key_distance"] is not None else 99,
                abs(float(candidate["energy_step"]))
                if candidate["energy_step"] is not None
                else float("inf"),
            )
        )

        return {
            "track_id": track_id,
            "pool_size": len(pool_ids),
            "scored": len(candidates),
            "candidates": candidates[:top_n],
        }
