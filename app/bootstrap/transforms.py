"""FastMCP transform registration helpers."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp.server.transforms.tool_transform import ToolTransform
from fastmcp.tools.tool_transform import ArgTransformConfig, ToolTransformConfig


def build_pre_constructor_transforms(_logger: logging.Logger | None = None) -> list[Any]:
    """Build transforms passed into the FastMCP constructor.

    BM25SearchTransform was removed because it forces Claude Code to call
    all tools via a ``run_tool`` proxy, which shows "Run Tool" in the UI
    instead of the actual tool name/title.  The native tag-based visibility
    system (``mcp.disable(tags=...)``) is used instead — see
    ``visibility.py``.

    ``build_set`` / ``rebuild_set`` are removed; the declarative flow uses
    ``commit_set_version`` instead — no transforms needed.
    """
    return [
        ToolTransform(
            {
                "score_transitions": ToolTransformConfig(
                    description=(
                        "Score how well tracks blend together. "
                        "Use mode='set' to audit all transitions in a set, "
                        "'pair' to check two specific tracks, "
                        "'track_candidates' to find best neighbors for a track."
                    ),
                    arguments={
                        "top_n": ArgTransformConfig(hide=True, default=10),
                    },
                ),
                "manage_set": ToolTransformConfig(
                    arguments={
                        "data": ArgTransformConfig(
                            description=(
                                "Action payload dict. "
                                "create: {name, template_name?}. "
                                "update: {id, name?, template_name?}. "
                                "delete: {id}. "
                                "add_constraint: {id, constraint_type, value}. "
                                "add_feedback: {id, feedback}."
                            ),
                        ),
                    },
                ),
                "manage_playlist": ToolTransformConfig(
                    arguments={
                        "data": ArgTransformConfig(
                            description=(
                                "Action payload dict. "
                                "create: {name, description?}. "
                                "update: {id, name?, description?}. "
                                "delete: {id}. "
                                "add_tracks: provide track_refs. "
                                "remove_tracks: provide track_refs. "
                                "reorder: provide positions."
                            ),
                        ),
                    },
                ),
                "manage_tracks": ToolTransformConfig(
                    arguments={
                        "data": ArgTransformConfig(
                            description=(
                                "Action payload dict. "
                                "create: {title, artist?, duration_ms?}. "
                                "update: {id, title?, artist?}. "
                                "archive/unarchive: {id}."
                            ),
                        ),
                    },
                ),
                "deliver_set": ToolTransformConfig(
                    description=(
                        "Export a DJ set to files and optionally sync to Yandex Music. "
                        "Generates M3U8 playlist, copies audio files, and pushes to YM."
                    ),
                ),
                "sync_playlist": ToolTransformConfig(
                    description=(
                        "Synchronize a playlist between local DB and Yandex Music. "
                        "direction='pull' imports from YM, 'push' exports to YM, "
                        "'diff' shows changes without applying."
                    ),
                ),
                "analyze_batch": ToolTransformConfig(
                    description=(
                        "Run audio analysis on multiple tracks. "
                        "Specify track_ids or playlist_id to analyze."
                    ),
                    arguments={
                        "batch_size": ArgTransformConfig(hide=True, default=10),
                    },
                ),
                "import_tracks": ToolTransformConfig(
                    description=(
                        "Import tracks from Yandex Music or other sources into the local library. "
                        "Provide track references (YM URLs, IDs, or search queries)."
                    ),
                ),
                "expand_platform_playlist": ToolTransformConfig(
                    description=(
                        "Find similar tracks on the active music platform and add them "
                        "to a playlist. "
                        "Uses track radio and similarity algorithms to discover new music."
                    ),
                ),
                "platform_playlists": ToolTransformConfig(
                    description=(
                        "Manage playlists on the active music platform. "
                        "action: get, get_tracks, list, create, rename, "
                        "delete, add_tracks, remove_tracks."
                    ),
                ),
                "platform_liked_tracks": ToolTransformConfig(
                    description=(
                        "Manage liked tracks on the active music platform. "
                        "action: get_liked (list all), add (like tracks), remove (unlike tracks)."
                    ),
                ),
                "track_feedback": ToolTransformConfig(
                    description=(
                        "Record subjective feedback on tracks. "
                        "action: like, ban, rate (1-5), get, list_liked, list_banned."
                    ),
                ),
                "transition_history": ToolTransformConfig(
                    description=(
                        "Track which transitions have been played and how they went. "
                        "action: log, list, best_pairs, react."
                    ),
                ),
            }
        ),
    ]


def register_post_constructor_transforms(mcp: Any, logger: logging.Logger | None = None) -> None:
    """Register transforms that require the FastMCP instance."""
    try:
        from fastmcp.server.transforms import PromptsAsTools, ResourcesAsTools

        mcp.add_transform(ResourcesAsTools(mcp))
        mcp.add_transform(PromptsAsTools(mcp))
    except ImportError:
        log = logger or logging.getLogger(__name__)
        log.debug("Post-constructor transforms unavailable")
