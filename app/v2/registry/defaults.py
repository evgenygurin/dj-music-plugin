"""Register the 11 user-facing entities with their schemas + presets.

Handlers default to ``None``; Phase 3 assigns custom handlers for
``track`` (import), ``track_features`` (analyze/reanalyze),
``audio_file`` (download), ``transition`` (persist score),
``set_version`` (build snapshot).
"""

from __future__ import annotations

from app.v2.models.audio_file import DjLibraryItem
from app.v2.models.playlist import DjPlaylist
from app.v2.models.scoring_profile import ScoringProfile
from app.v2.models.set import DjSet, DjSetVersion
from app.v2.models.track import Track
from app.v2.models.track_affinity import TrackAffinity
from app.v2.models.track_features import TrackAudioFeaturesComputed
from app.v2.models.track_feedback import TrackFeedback
from app.v2.models.transition import Transition
from app.v2.models.transition_history import TransitionHistory
from app.v2.registry.entity import EntityConfig, EntityRegistry
from app.v2.schemas.audio_file import (
    AudioFileCreate,
    AudioFileFilter,
    AudioFileUpdate,
    AudioFileView,
)
from app.v2.schemas.playlist import (
    PlaylistCreate,
    PlaylistFilter,
    PlaylistUpdate,
    PlaylistView,
)
from app.v2.schemas.scoring_profile import (
    ScoringProfileCreate,
    ScoringProfileFilter,
    ScoringProfileUpdate,
    ScoringProfileView,
)
from app.v2.schemas.set import (
    SetCreate,
    SetFilter,
    SetUpdate,
    SetVersionCreate,
    SetVersionView,
    SetView,
)
from app.v2.schemas.track import TrackCreate, TrackFilter, TrackUpdate, TrackView
from app.v2.schemas.track_affinity import (
    TrackAffinityCreate,
    TrackAffinityFilter,
    TrackAffinityUpdate,
    TrackAffinityView,
)
from app.v2.schemas.track_features import (
    TrackFeaturesCreate,
    TrackFeaturesFilter,
    TrackFeaturesUpdate,
    TrackFeaturesView,
)
from app.v2.schemas.track_feedback import (
    TrackFeedbackCreate,
    TrackFeedbackFilter,
    TrackFeedbackUpdate,
    TrackFeedbackView,
)
from app.v2.schemas.transition import (
    TransitionCreate,
    TransitionFilter,
    TransitionUpdate,
    TransitionView,
)
from app.v2.schemas.transition_history import (
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
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "title"],
                "summary": ["id", "title", "duration_ms", "status"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("title", "sort_title"),
            filterable_fields={
                "id": ("eq", "in"),
                "title": ("icontains",),
                "status": ("eq", "in"),
            },
            sortable_fields=("id", "title", "duration_ms"),
            relations={"artists": "artists", "features": "track_audio_features_computed"},
            tags=frozenset({"namespace:library"}),
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
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "name"],
                "summary": ["id", "name", "source_of_truth"],
                "full": "*",
            },
            default_preset="id",
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
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "name"],
                "summary": ["id", "name", "template_name", "target_duration_ms"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("name",),
            filterable_fields={
                "id": ("eq", "in"),
                "name": ("icontains",),
                "template_name": ("eq",),
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
            filter_schema=SetFilter,
            create_schema=SetVersionCreate,
            update_schema=SetUpdate,
            allowed_ops=frozenset({"list", "get", "create", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "set_id", "version_label", "quality_score"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("version_label",),
            filterable_fields={"set_id": ("eq", "in")},
            sortable_fields=("id", "quality_score"),
            relations={"items": "dj_set_items"},
            tags=frozenset({"namespace:sets"}),
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
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_id", "file_path", "file_size"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("file_path",),
            filterable_fields={"id": ("eq", "in"), "track_id": ("eq", "in")},
            sortable_fields=("id", "file_size"),
            relations={"beatgrids": "dj_beatgrids"},
            tags=frozenset({"namespace:library"}),
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
            allowed_ops=frozenset({"list", "get", "create", "update"}),
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
            default_preset="id",
            searchable_fields=(),
            filterable_fields={
                "track_id": ("eq", "in"),
                "bpm": ("gte", "lte", "range"),
                "mood": ("eq", "in"),
            },
            sortable_fields=("track_id", "bpm"),
            relations={},
            tags=frozenset({"namespace:analysis"}),
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
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": [
                    "id",
                    "from_track_id",
                    "to_track_id",
                    "overall_score",
                    "style",
                ],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=(),
            filterable_fields={
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "overall_score": ("gte", "lte"),
            },
            sortable_fields=("id", "overall_score"),
            relations={},
            tags=frozenset({"namespace:transitions"}),
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
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": [
                    "id",
                    "from_track_id",
                    "to_track_id",
                    "overall_score",
                    "reaction",
                ],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=(),
            filterable_fields={
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "reaction": ("eq",),
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
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_id", "kind", "rating"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=(),
            filterable_fields={"track_id": ("eq", "in"), "kind": ("eq",)},
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
            allowed_ops=frozenset({"list", "get", "create", "update"}),
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
            default_preset="id",
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
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "name"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("name",),
            filterable_fields={"name": ("eq", "icontains")},
            sortable_fields=("id", "name"),
            relations={},
            tags=frozenset({"namespace:scoring"}),
        )
    )
