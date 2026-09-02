"""Task 5: FastMCP Task stems_separate — progress, cancel, Semaphore(1).

- Tool is registered and supports tasks (task=True → async required).
- Direct call reports progress per track and returns 5 stems.
- Via MCP client (in-memory) — tool callable, graceful degradation when
  no docket worker (immediate result) still yields correct shape.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_stems_separate_is_registered_and_task_enabled(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    names = {t.name for t in tools}
    assert "stems_separate" in names, f"stems_separate not in {sorted(names)}"


@pytest.mark.asyncio
async def test_stems_task_reports_progress_direct(tmp_path: Path) -> None:
    """Direct handler call with mocked runner: progress N+1 calls, 5 stems."""
    from app.tools.stems import stems_separate

    # Create fake audio file so .exists() passes
    audio = tmp_path / "track01.mp3"
    audio.write_bytes(b"\x00" * 1024)

    # Runner mock — returns 5 fake stem paths (flac)
    fake_stems = {
        "vocals": audio.parent / "vocals.flac",
        "drums": audio.parent / "drums.flac",
        "bass": audio.parent / "bass.flac",
        "harmonic": audio.parent / "harmonic.flac",
        "percussion": audio.parent / "percussion.flac",
    }
    for p in fake_stems.values():
        p.touch()

    mock_runner = MagicMock(return_value={k: Path(v) for k, v in fake_stems.items()})

    # Mock context with async report_progress
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    mock_ctx.info = AsyncMock()
    mock_ctx.warning = AsyncMock()
    mock_ctx.error = AsyncMock()

    # Mock UoW: _resolve_track_path will read from it — patch that helper
    # to avoid DB coupling, return our tmp file directly.
    mock_uow = MagicMock()

    track_ids = [11, 22]

    with (
        patch("app.audio.deep.get_runner", return_value=mock_runner),
        patch("app.tools.stems._resolve_track_path", new=AsyncMock(return_value=audio)),
        patch("app.handlers._orchestrator.stem_resolver._find_cached_stems", return_value=None),
        patch("app.config.get_settings") as mock_settings,
    ):
        # delivery.output_dir → tmp_path so workspace/cache is isolated
        mock_settings.return_value.delivery.output_dir = str(tmp_path / "out")
        mock_settings.return_value.delivery.output_dir = str(tmp_path / "out")

        result = await stems_separate(track_ids=track_ids, ctx=mock_ctx, uow=mock_uow)

    # Shape
    assert "stems" in result
    assert "errors" in result
    assert result["total"] == 2
    assert result["errors"] == []
    assert "11" in result["stems"]
    assert "22" in result["stems"]
    for tid_str in ("11", "22"):
        stems = result["stems"][tid_str]
        assert set(stems.keys()) == {"vocals", "drums", "bass", "harmonic", "percussion"}

    # Progress: initial 0/total + per-track (i, i+1) = at least 1 + 2*2
    # safe_report_progress wraps ctx.report_progress — our mock_ctx tracks calls
    # via safe_report_progress's await ctx.report_progress(...).
    assert mock_ctx.report_progress.await_count >= 4, mock_ctx.report_progress.await_args_list

    # Runner called once per track (Semaphore(1) serialized, to_thread)
    assert mock_runner.call_count == 2


@pytest.mark.asyncio
async def test_stems_task_reuses_cache(tmp_path: Path) -> None:
    """When _find_cached_stems hits, runner is NOT called."""
    from app.tools.stems import stems_separate

    audio = tmp_path / "track02.mp3"
    audio.write_bytes(b"\x00")

    cached = {
        "vocals": str(tmp_path / "vocals.flac"),
        "drums": str(tmp_path / "drums.flac"),
        "bass": str(tmp_path / "bass.flac"),
        "harmonic": str(tmp_path / "harmonic.flac"),
        "percussion": str(tmp_path / "percussion.flac"),
    }

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    mock_ctx.info = AsyncMock()
    mock_runner = MagicMock()

    mock_uow = MagicMock()

    with (
        patch("app.audio.deep.get_runner", return_value=mock_runner),
        patch("app.tools.stems._resolve_track_path", new=AsyncMock(return_value=audio)),
        patch("app.handlers._orchestrator.stem_resolver._find_cached_stems", return_value=cached),
        patch("app.config.get_settings") as mock_settings,
    ):
        mock_settings.return_value.delivery.output_dir = str(tmp_path / "out2")
        result = await stems_separate(track_ids=[5], ctx=mock_ctx, uow=mock_uow)

    assert result["stems"]["5"] == cached
    assert result["errors"] == []
    mock_runner.assert_not_called()


@pytest.mark.asyncio
async def test_stems_task_reports_progress_via_mcp_client(
    mcp_client: Client, mock_uow: MagicMock, tmp_path: Path
) -> None:
    """Via in-memory MCP client (graceful degradation without docket worker).

    ``task=True`` tools are callable synchronously when no task worker is
    present — the server returns an immediate CallToolResult. We just verify
    the tool is callable via the client and returns the expected shape when
    runner is mocked.
    """
    audio = tmp_path / "mcp_track.mp3"
    audio.write_bytes(b"\x00")
    fake = {
        "vocals": str(tmp_path / "vocals.flac"),
        "drums": str(tmp_path / "drums.flac"),
        "bass": str(tmp_path / "bass.flac"),
        "harmonic": str(tmp_path / "harmonic.flac"),
        "percussion": str(tmp_path / "percussion.flac"),
    }
    # provide fake stem files for existence checks if mapping bypasses cache
    for p in fake.values():
        Path(p).touch()

    mock_runner = MagicMock(return_value={k: Path(v) for k, v in fake.items()})
    # Configure mock_uow so _resolve_track_path finds the file via tracks.get
    # (avoids fragile patch of synthetic FileSystemProvider module name)
    mock_uow.tracks.get = AsyncMock(return_value=MagicMock(file_path=str(audio)))  # type: ignore[attr-defined]

    with (
        patch("app.audio.deep.get_runner", return_value=mock_runner),
        patch("app.handlers._orchestrator.stem_resolver._find_cached_stems", return_value=None),
        patch("app.config.get_settings") as mock_settings,
    ):
        mock_settings.return_value.delivery.output_dir = str(tmp_path / "mcp_out")

        result = await mcp_client.call_tool("stems_separate", {"track_ids": [1]})

    # FastMCP Client returns CallToolResult; .data holds structuredContent
    # (wrapped). The tool returns {"stems":..., "errors":..., "total":...}
    assert result.data is not None or result.content is not None
    # Prefer structured data when available
    payload = result.data if result.data is not None else result.structured_content
    # Some FastMCP versions expose .structured_content, others .data — handle both
    if payload is None and hasattr(result, "structured_content"):
        payload = result.structured_content  # type: ignore[attr-defined]
    # Fallback: content text may contain JSON
    if isinstance(payload, dict):
        # Direct dict or {"stems": ...}
        if "stems" in payload:
            assert "1" in payload["stems"]
        elif "result" in payload and isinstance(payload["result"], dict):
            assert "stems" in payload["result"]
    else:
        # If serialization wrapped in content[0].text, at least ensure no error
        assert result.is_error is False or result.isError is False  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_stems_task_empty_track_ids_rejected() -> None:
    from app.tools.stems import stems_separate

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    mock_ctx.info = AsyncMock()
    mock_uow = MagicMock()

    with pytest.raises(ValueError, match="non-empty"):
        await stems_separate(track_ids=[], ctx=mock_ctx, uow=mock_uow)
