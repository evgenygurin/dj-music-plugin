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
                "id": ("eq", "in"),
                "title": ("icontains",),
                "status": ("eq", "in"),
            },
            sortable_fields=("id", "title", "duration_ms"),
            relations={"artists": "artists", "features": "track_audio_features_computed"},
            tags=frozenset({"namespace:library"}),
            create_handler=track_import_handler,
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
            filterable_fields={"id": ("eq", "in"), "name": ("icontains",)},
            sortable_fields=("id", "name"),
            relations={"items": "dj_playlist_items"},
            tags=frozenset({"namespace:library"}),
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
                "id": ("eq", "in"),
                "name": ("eq", "icontains"),
                "template_name": ("eq", "in"),
                "source_playlist_id": ("eq", "in"),
                "target_bpm_min": ("gte", "lte"),
                "target_bpm_max": ("gte", "lte"),
                "target_duration_ms": ("gte", "lte"),
            },
            sortable_fields=("id", "name"),
            relations={"versions": "dj_set_versions"},
            tags=frozenset({"namespace:sets"}),
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
                "id": ("eq", "in"),
                "set_id": ("eq", "in"),
                "quality_score": ("gte", "lte", "range"),
                "label": ("icontains",),
            },
            sortable_fields=("id", "quality_score"),
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
                "file_size": ("gte", "lte", "range"),
            },
            sortable_fields=("id", "file_size"),
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
                "mood": ("eq", "in"),
            },
            sortable_fields=("track_id", "bpm"),
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
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "overall_quality": ("gte", "lte", "range"),
                "hard_reject": ("eq",),
            },
            sortable_fields=("id", "overall_quality"),
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
            },
            sortable_fields=("id", "overall_score"),
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
                "summary": ["id", "track_id", "kind", "rating"],
                "full": "*",
            },
            default_preset="full",
            searchable_fields=(),
            filterable_fields={
                "track_id": ("eq", "in"),
                "kind": ("eq", "in"),
                "rating": ("eq", "gte", "lte", "in"),
            },
            sortable_fields=("id",),
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
                "track_a_id": ("eq",),
                "track_b_id": ("eq",),
                "avg_score": ("gte",),
            },
            sortable_fields=("id", "avg_score"),
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
            filterable_fields={"name": ("eq", "icontains")},
            sortable_fields=("id", "name"),
            relations={},
            tags=frozenset({"namespace:scoring"}),
        )
    )
