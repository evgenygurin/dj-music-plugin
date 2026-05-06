"""Register the 11 user-facing entities with their schemas + presets.

Handlers default to ``None``; Phase 3 assigns custom handlers for
``track`` (import), ``track_features`` (analyze/reanalyze),
``audio_file`` (download), ``transition`` (persist score),
``set_version`` (build snapshot).
"""

from __future__ import annotations

from app.handlers.audio_file_download import audio_file_download_handler
from app.handlers.set_version_build import set_version_build_handler
from app.handlers.track_features_analyze import track_features_analyze_handler
from app.handlers.track_features_reanalyze import track_features_reanalyze_handler
from app.handlers.track_import import track_import_handler
from app.handlers.transition_persist import transition_persist_handler
from app.models.audio_file import DjLibraryItem
from app.models.playlist import DjPlaylist
from app.models.scoring_profile import ScoringProfile
from app.models.set import DjSet, DjSetVersion
from app.models.track import Track
from app.models.track_affinity import TrackAffinity
from app.models.track_features import TrackAudioFeaturesComputed
from app.models.track_feedback import TrackFeedback
from app.models.transition import Transition
from app.models.transition_history import TransitionHistory
from app.registry.entity import EntityConfig, EntityRegistry
from app.schemas.audio_file import (
    AudioFileCreate,
    AudioFileFilter,
    AudioFileUpdate,
    AudioFileView,
)
from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistFilter,
    PlaylistUpdate,
    PlaylistView,
)
from app.schemas.scoring_profile import (
    ScoringProfileCreate,
    ScoringProfileFilter,
    ScoringProfileUpdate,
    ScoringProfileView,
)
from app.schemas.set import (
    SetCreate,
    SetFilter,
    SetUpdate,
    SetVersionCreate,
    SetVersionFilter,
    SetVersionView,
    SetView,
)
from app.schemas.track import TrackCreate, TrackFilter, TrackUpdate, TrackView
from app.schemas.track_affinity import (
    TrackAffinityCreate,
    TrackAffinityFilter,
    TrackAffinityUpdate,
    TrackAffinityView,
)
from app.schemas.track_features import (
    TrackFeaturesCreate,
    TrackFeaturesFilter,
    TrackFeaturesUpdate,
    TrackFeaturesView,
)
from app.schemas.track_feedback import (
    TrackFeedbackCreate,
    TrackFeedbackFilter,
    TrackFeedbackUpdate,
    TrackFeedbackView,
)
from app.schemas.transition import (
    TransitionCreate,
    TransitionFilter,
    TransitionUpdate,
    TransitionView,
)
from app.schemas.transition_history import (
    TransitionHistoryCreate,
    TransitionHistoryFilter,
    TransitionHistoryUpdate,
    TransitionHistoryView,
)


async def _enrich_playlist_view(uow: object, row: object, view: dict) -> dict:  # type: ignore[type-arg]
    """Populate ``PlaylistView.item_count`` (audit iter 46 / T-44)."""
    pid = getattr(row, "id", None)
    if pid is None:
        return view
    view["item_count"] = await uow.playlists.item_count(pid)  # type: ignore[attr-defined]
    return view


async def _enrich_track_view(uow: object, row: object, view: dict) -> dict:  # type: ignore[type-arg]
    """Populate ``TrackView.primary_artist_name`` (smoke test 2026-05-07).

    Mirrors what ``local://tracks/{id}`` resource has been doing since
    audit O-1: ``primary_artist_name`` is derived from the
    ``track_artists`` relationship, not a column on ``tracks``.
    Without this enricher ``entity_get(track, …)`` and
    ``entity_list(track, …)`` returned ``primary_artist_name=null`` for
    every row even when the resource showed the real name.
    """
    tid = getattr(row, "id", None)
    if tid is None:
        return view
    view["primary_artist_name"] = await uow.tracks.get_primary_artist_name(tid)  # type: ignore[attr-defined]
    return view


async def _enrich_set_view(uow: object, row: object, view: dict) -> dict:  # type: ignore[type-arg]
    """Populate ``SetView.version_count`` (audit iter 46 / T-44)."""
    sid = getattr(row, "id", None)
    if sid is None:
        return view
    view["version_count"] = await uow.sets.version_count(sid)  # type: ignore[attr-defined]
    return view


def register_default_entities() -> None:
    EntityRegistry.register(
        EntityConfig(
            name="track",
            model=Track,
            repo_attr="tracks",
            view_schema=TrackView,
            filter_schema=TrackFilter,
            create_schema=TrackCreate,
            update_schema=TrackUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "title"],
                "summary": ["id", "title", "duration_ms", "status"],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=("title", "sort_title"),
            filterable_fields={
                "id": ("eq", "in", "gt", "gte", "lt", "lte"),
                "title": ("icontains", "contains"),
                "sort_title": ("icontains",),
                "status": ("eq", "in"),
                "duration_ms": ("gte", "lte"),
                "has_features": ("eq",),
            },
            sortable_fields=(
                "id",
                "title",
                "sort_title",
                "duration_ms",
                "status",
                "created_at",
                "updated_at",
            ),
            relations={"artists": "artists", "features": "track_audio_features_computed"},
            tags=frozenset({"namespace:library"}),
            create_handler=track_import_handler,
            view_enricher=_enrich_track_view,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="playlist",
            model=DjPlaylist,
            repo_attr="playlists",
            view_schema=PlaylistView,
            filter_schema=PlaylistFilter,
            create_schema=PlaylistCreate,
            update_schema=PlaylistUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "name"],
                "summary": ["id", "name", "source_of_truth"],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=("name",),
            filterable_fields={
                "id": ("eq", "in", "gt", "gte", "lt", "lte"),
                "name": ("eq", "icontains", "startswith"),
                "source_of_truth": ("eq", "in"),
                "parent_id": ("eq", "in", "isnull"),
                "source_app": ("eq", "in", "isnull"),
                "platform_ids": ("icontains", "isnull"),
                # ``item_count`` is a correlated subquery column on
                # ``DjPlaylist`` (see ``app/models/playlist.py``).
                "item_count": ("eq", "gt", "gte", "lt", "lte"),
            },
            sortable_fields=(
                "id",
                "name",
                "source_app",
                "item_count",
                "created_at",
                "updated_at",
            ),
            relations={"items": "dj_playlist_items"},
            tags=frozenset({"namespace:library"}),
            view_enricher=_enrich_playlist_view,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="set",
            model=DjSet,
            repo_attr="sets",
            view_schema=SetView,
            filter_schema=SetFilter,
            create_schema=SetCreate,
            update_schema=SetUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "name"],
                "summary": ["id", "name", "template_name", "target_duration_ms"],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=("name",),
            filterable_fields={
                "id": ("eq", "in", "gt", "gte", "lt", "lte"),
                "name": ("eq", "icontains"),
                "template_name": ("eq", "in"),
                "source_playlist_id": ("eq", "in"),
                "target_bpm_min": ("gte", "lte"),
                "target_bpm_max": ("gte", "lte"),
                "target_duration_ms": ("gte", "lte"),
            },
            sortable_fields=(
                "id",
                "name",
                "template_name",
                "target_duration_ms",
                "created_at",
                "updated_at",
            ),
            relations={"versions": "dj_set_versions"},
            tags=frozenset({"namespace:sets"}),
            view_enricher=_enrich_set_view,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="set_version",
            model=DjSetVersion,
            repo_attr="set_versions",
            view_schema=SetVersionView,
            filter_schema=SetVersionFilter,
            create_schema=SetVersionCreate,
            update_schema=SetUpdate,
            allowed_ops=frozenset({"list", "get", "create", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "set_id", "label", "quality_score"],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=("label",),
            filterable_fields={
                "id": ("eq", "in", "gt", "gte", "lt", "lte"),
                "set_id": ("eq", "in"),
                "quality_score": ("gte", "lte", "range"),
                "label": ("eq", "icontains"),
            },
            sortable_fields=("id", "label", "quality_score", "created_at"),
            relations={"items": "dj_set_items"},
            tags=frozenset({"namespace:sets"}),
            create_handler=set_version_build_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="audio_file",
            model=DjLibraryItem,
            repo_attr="audio_files",
            view_schema=AudioFileView,
            filter_schema=AudioFileFilter,
            create_schema=AudioFileCreate,
            update_schema=AudioFileUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_id", "file_path", "file_size"],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=("file_path",),
            filterable_fields={
                "id": ("eq", "in"),
                "track_id": ("eq", "in"),
                "file_path": ("icontains",),
                "file_uri": ("icontains",),
                "file_hash": ("eq", "isnull"),
                "file_size": ("gte", "lte", "range"),
                "bitrate": ("eq", "gte", "lte"),
                "sample_rate": ("eq", "in"),
                "channels": ("eq",),
                "mime_type": ("eq", "in"),
                "source_app": ("eq", "in", "isnull"),
            },
            sortable_fields=("id", "track_id", "file_size", "bitrate", "created_at"),
            relations={"beatgrids": "dj_beatgrids"},
            tags=frozenset({"namespace:library"}),
            create_handler=audio_file_download_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_features",
            model=TrackAudioFeaturesComputed,
            repo_attr="track_features",
            view_schema=TrackFeaturesView,
            filter_schema=TrackFeaturesFilter,
            create_schema=TrackFeaturesCreate,
            update_schema=TrackFeaturesUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "aggregate"}),
            field_presets={
                "id": ["track_id"],
                "scoring": [
                    "track_id",
                    "bpm",
                    "key_code",
                    "integrated_lufs",
                    "energy_mean",
                    "spectral_centroid_hz",
                    "hp_ratio",
                    "kick_prominence",
                    "mood",
                ],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=(),
            filterable_fields={
                "track_id": ("eq", "in"),
                "analysis_level": ("eq", "gte", "lt"),
                "bpm": ("eq", "gte", "lte", "range"),
                "key_code": ("eq", "in", "range"),
                "integrated_lufs": ("gte", "lte", "range"),
                "mood": ("eq", "in", "isnull"),
                "mood_confidence": ("gte", "lte"),
                "energy_mean": ("gte", "lte"),
                "spectral_centroid_hz": ("gte", "lte"),
                "hp_ratio": ("gte", "lte"),
                "kick_prominence": ("gte", "lte"),
                "true_peak_db": ("gte", "lte"),
                "key_confidence": ("gte", "lte"),
                "atonality": ("eq",),
                "variable_tempo": ("eq",),
                "danceability": ("gte", "lte"),
                "dissonance_mean": ("gte", "lte"),
                "bpm_confidence": ("gte", "lte"),
                "bpm_stability": ("gte", "lte"),
                "onset_rate": ("gte", "lte"),
                "pulse_clarity": ("gte", "lte"),
            },
            sortable_fields=(
                "track_id",
                "bpm",
                "key_code",
                "analysis_level",
                "integrated_lufs",
                "energy_mean",
                "mood",
                "mood_confidence",
            ),
            relations={},
            tags=frozenset({"namespace:analysis"}),
            create_handler=track_features_analyze_handler,
            update_handler=track_features_reanalyze_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="transition",
            model=Transition,
            repo_attr="transitions",
            view_schema=TransitionView,
            filter_schema=TransitionFilter,
            create_schema=TransitionCreate,
            update_schema=TransitionUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": [
                    "id",
                    "from_track_id",
                    "to_track_id",
                    "overall_quality",
                    "fx_type",
                ],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=(),
            filterable_fields={
                "id": ("eq", "in", "gt", "gte", "lt", "lte"),
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "overall_quality": ("gte", "lte", "range"),
                "hard_reject": ("eq",),
                "reject_reason": ("icontains", "isnull"),
                "fx_type": ("eq", "in"),
                "bpm_score": ("gte", "lte"),
                "harmonics_score": ("gte", "lte"),
                "energy_score": ("gte", "lte"),
                "bass_score": ("gte", "lte"),
                "drums_score": ("gte", "lte"),
                "vocals_score": ("gte", "lte"),
                "key_distance_weighted": ("gte", "lte"),
                "low_conflict_score": ("gte", "lte"),
                "transition_bars": ("eq", "in", "gte", "lte"),
                "overlap_ms": ("gte", "lte"),
            },
            sortable_fields=(
                "id",
                "from_track_id",
                "to_track_id",
                "overall_quality",
                "hard_reject",
                "fx_type",
                "transition_bars",
                "overlap_ms",
                "created_at",
            ),
            relations={},
            tags=frozenset({"namespace:transitions"}),
            create_handler=transition_persist_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="transition_history",
            model=TransitionHistory,
            repo_attr="transition_history",
            view_schema=TransitionHistoryView,
            filter_schema=TransitionHistoryFilter,
            create_schema=TransitionHistoryCreate,
            update_schema=TransitionHistoryUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": [
                    "id",
                    "from_track_id",
                    "to_track_id",
                    "overall_score",
                    "user_reaction",
                ],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=(),
            filterable_fields={
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "user_reaction": ("eq",),
                "session_id": ("eq",),
                "overall_score": ("gte", "lte", "range"),
                "style": ("eq", "in", "icontains"),
                "duration_sec": ("gte", "lte", "range"),
                "tempo_match_ratio": ("gte", "lte"),
                "bpm_score": ("gte", "lte"),
                "harmonics_score": ("gte", "lte"),
                "energy_score": ("gte", "lte"),
                "bass_score": ("gte", "lte"),
                "drums_score": ("gte", "lte"),
                "vocals_score": ("gte", "lte"),
            },
            sortable_fields=(
                "id",
                "from_track_id",
                "to_track_id",
                "overall_score",
                "user_reaction",
                "style",
                "duration_sec",
                "created_at",
            ),
            relations={},
            tags=frozenset({"namespace:transitions"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_feedback",
            model=TrackFeedback,
            repo_attr="track_feedback",
            view_schema=TrackFeedbackView,
            filter_schema=TrackFeedbackFilter,
            create_schema=TrackFeedbackCreate,
            update_schema=TrackFeedbackUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_id", "status", "rating"],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=(),
            filterable_fields={
                "track_id": ("eq", "in"),
                "status": ("eq", "in"),
                "rating": ("eq", "gte", "lte", "in"),
                "play_count": ("gte", "lte"),
                "skip_count": ("gte", "lte"),
            },
            sortable_fields=(
                "id",
                "track_id",
                "status",
                "rating",
                "play_count",
                "skip_count",
                "created_at",
                "updated_at",
            ),
            relations={},
            tags=frozenset({"namespace:feedback"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_affinity",
            model=TrackAffinity,
            repo_attr="track_affinity",
            view_schema=TrackAffinityView,
            filter_schema=TrackAffinityFilter,
            create_schema=TrackAffinityCreate,
            update_schema=TrackAffinityUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": [
                    "id",
                    "track_a_id",
                    "track_b_id",
                    "avg_score",
                    "play_count",
                ],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=(),
            filterable_fields={
                "id": ("eq", "in", "gt", "gte", "lt", "lte"),
                "track_a_id": ("eq", "in"),
                "track_b_id": ("eq", "in"),
                "avg_score": ("gte", "lte", "range"),
                "play_count": ("gte", "lte"),
                "like_count": ("gte", "lte"),
                "ban_count": ("gte", "lte"),
                "skip_count": ("gte", "lte"),
                "net_sentiment": ("gte", "lte", "range"),
            },
            sortable_fields=(
                "id",
                "avg_score",
                "play_count",
                "net_sentiment",
                "last_played_at",
            ),
            relations={},
            tags=frozenset({"namespace:feedback"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="scoring_profile",
            model=ScoringProfile,
            repo_attr="scoring_profiles",
            view_schema=ScoringProfileView,
            filter_schema=ScoringProfileFilter,
            create_schema=ScoringProfileCreate,
            update_schema=ScoringProfileUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "name"],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=("name",),
            filterable_fields={
                "id": ("eq", "in"),
                "name": ("eq", "icontains"),
                "bpm_weight": ("gte", "lte"),
                "harmonics_weight": ("gte", "lte"),
                "energy_weight": ("gte", "lte"),
                "bass_weight": ("gte", "lte"),
                "drums_weight": ("gte", "lte"),
                "vocals_weight": ("gte", "lte"),
            },
            sortable_fields=("id", "name", "created_at", "updated_at"),
            relations={},
            tags=frozenset({"namespace:scoring"}),
        )
    )
