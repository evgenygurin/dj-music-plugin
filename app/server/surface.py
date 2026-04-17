"""Phase 1 domain-manager facade over v1 generic dispatchers.

Each manager is a ``ToolTransformConfig`` that renames a raw dispatcher
and hides the ``entity``/``provider`` argument. The facade is zero-dup —
the handler chain remains the raw dispatcher's.

``transitions_score`` is a composite registered separately as a
standalone ``@tool`` under ``app/tools/domain/``, not a ``ToolTransform``.

Public API: ``register_managers(mcp)``. Called from ``build_mcp_server``
after ``register_post_constructor_transforms``.
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.transforms import ToolTransform
from fastmcp.tools.tool_transform import ArgTransformConfig, ToolTransformConfig

# Placeholder configs — real definitions added in Task 4.
TRACKS_LIST: ToolTransformConfig = ToolTransformConfig(
    name="tracks_list",
    description="placeholder",
    tags={"namespace:domain:tracks", "read"},
    version="2.0",
    arguments={"entity": ArgTransformConfig(hide=True, default="track")},
)
TRACKS_GET: ToolTransformConfig = ToolTransformConfig(
    name="tracks_get",
    description="placeholder",
    tags={"namespace:domain:tracks", "read"},
    version="2.0",
    arguments={"entity": ArgTransformConfig(hide=True, default="track")},
)
TRACKS_IMPORT: ToolTransformConfig = ToolTransformConfig(
    name="tracks_import",
    description="placeholder",
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    arguments={"entity": ArgTransformConfig(hide=True, default="track")},
)
TRACKS_ANALYZE: ToolTransformConfig = ToolTransformConfig(
    name="tracks_analyze",
    description="placeholder",
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    arguments={"entity": ArgTransformConfig(hide=True, default="track_features")},
)
TRACKS_AUDIO_DOWNLOAD: ToolTransformConfig = ToolTransformConfig(
    name="tracks_audio_download",
    description="placeholder",
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    arguments={"entity": ArgTransformConfig(hide=True, default="audio_file")},
)
PLAYLISTS_LIST: ToolTransformConfig = ToolTransformConfig(
    name="playlists_list",
    description="placeholder",
    tags={"namespace:domain:playlists", "read"},
    version="2.0",
    arguments={"entity": ArgTransformConfig(hide=True, default="playlist")},
)
PLAYLISTS_SYNC: ToolTransformConfig = ToolTransformConfig(
    name="playlists_sync",
    description="placeholder",
    tags={"namespace:domain:playlists:write", "write"},
    version="2.0",
    arguments={},
)
SETS_BUILD: ToolTransformConfig = ToolTransformConfig(
    name="sets_build",
    description="placeholder",
    tags={"namespace:domain:sets", "write"},
    version="2.0",
    arguments={"entity": ArgTransformConfig(hide=True, default="set_version")},
)
SETS_GET: ToolTransformConfig = ToolTransformConfig(
    name="sets_get",
    description="placeholder",
    tags={"namespace:domain:sets", "read"},
    version="2.0",
    arguments={"entity": ArgTransformConfig(hide=True, default="set")},
)
LIBRARY_AGGREGATE: ToolTransformConfig = ToolTransformConfig(
    name="library_aggregate",
    description="placeholder",
    tags={"namespace:domain:library", "read"},
    version="2.0",
    arguments={},
)
# TRANSITIONS_SCORE is a composite — no ToolTransformConfig.
# It lives as a standalone tool under app/tools/domain/transitions_score.py.

# Sentinel so the Phase 1 test for "all managers have a module-level constant"
# sees TRANSITIONS_SCORE. The real tool lives in app/tools/domain/transitions_score.py
# (added in Task 5) because it's a composite — ToolTransform can't express it.
TRANSITIONS_SCORE: None = None


def register_managers(mcp: FastMCP) -> None:
    """Attach v2.0 domain managers as ToolTransform over v1 dispatchers.

    One ToolTransform per manager (so one original dispatcher can feed many
    managers). The composite ``transitions_score`` is auto-discovered by
    the FileSystemProvider; nothing to register here.
    """
    mcp.add_transform(ToolTransform({"entity_list": TRACKS_LIST}))
    mcp.add_transform(ToolTransform({"entity_list": PLAYLISTS_LIST}))
    mcp.add_transform(ToolTransform({"entity_get": TRACKS_GET}))
    mcp.add_transform(ToolTransform({"entity_get": SETS_GET}))
    mcp.add_transform(ToolTransform({"entity_create": TRACKS_IMPORT}))
    mcp.add_transform(ToolTransform({"entity_create": TRACKS_ANALYZE}))
    mcp.add_transform(ToolTransform({"entity_create": TRACKS_AUDIO_DOWNLOAD}))
    mcp.add_transform(ToolTransform({"entity_create": SETS_BUILD}))
    mcp.add_transform(ToolTransform({"entity_aggregate": LIBRARY_AGGREGATE}))
    mcp.add_transform(ToolTransform({"playlist_sync": PLAYLISTS_SYNC}))
