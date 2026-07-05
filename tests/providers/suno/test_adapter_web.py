"""SunoAdapter tests for the browser-session (suno_web) surface — no network."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.providers.suno.adapter import SunoAdapter
from app.shared.errors import ValidationError


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.api_call.return_value = {"id": "clip-1", "status": "queued"}
    client.create_generation.return_value = {
        "id": "batch-1",
        "status": "running",
        "clips": [{"id": "clip-a", "status": "submitted"}],
    }
    return client


@pytest.fixture
def web(mock_client: AsyncMock) -> SunoAdapter:
    return SunoAdapter(
        client=mock_client, default_model="chirp-auk-turbo", payload_mode="suno_web"
    )


def test_web_surface_is_expanded(web: SunoAdapter) -> None:
    for e in ("generation", "clip", "stem", "wav", "edit", "remaster", "persona", "playlist"):
        assert e in web.entities_supported
    assert {"extend", "concat"} <= set(web.operations_supported["generation"])
    assert set(web.operations_supported["edit"]) == {"crop", "fade", "reverse"}


async def test_extend_uses_generate_endpoint_with_task(
    web: SunoAdapter, mock_client: AsyncMock
) -> None:
    out = await web.write(
        "generation",
        "extend",
        {"continue_clip_id": "clip-x", "continue_at": 45, "prompt": "keep the roll going"},
    )
    payload = mock_client.create_generation.await_args.args[0]
    assert payload["task"] == "extend"
    assert payload["continue_clip_id"] == "clip-x"
    assert payload["continue_at"] == 45
    assert payload["gpt_description_prompt"] == "keep the roll going"
    assert out["generation_id"] == "clip-a"  # pollable clip id from batch


async def test_extend_requires_continue_params(web: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="continue_clip_id"):
        await web.write("generation", "extend", {"prompt": "x"})


async def test_concat_posts_clip_id(web: SunoAdapter, mock_client: AsyncMock) -> None:
    await web.write("generation", "concat", {"clip_id": "clip-9"})
    method, path = mock_client.api_call.await_args.args
    assert (method, path) == ("POST", "/api/generate/concat/v2/")
    assert mock_client.api_call.await_args.kwargs["json"] == {"clip_id": "clip-9"}


async def test_stem_create_empty_body_and_path(web: SunoAdapter, mock_client: AsyncMock) -> None:
    await web.write("stem", "create", {"clip_id": "clip-7"})
    _, path = mock_client.api_call.await_args.args
    assert path == "/api/edit/stems/clip-7/"
    assert mock_client.api_call.await_args.kwargs["json"] == {}


async def test_wav_create_accepts_204(web: SunoAdapter, mock_client: AsyncMock) -> None:
    mock_client.api_call.return_value = {}
    out = await web.write("wav", "create", {"clip_id": "clip-7"})
    assert mock_client.api_call.await_args.args[1] == "/api/gen/clip-7/convert_wav/"
    assert out["status"] == "accepted"


async def test_crop_builds_body_and_returns_action_clip(
    web: SunoAdapter, mock_client: AsyncMock
) -> None:
    mock_client.api_call.return_value = {"action_clip_id": "clip-cropped"}
    out = await web.write(
        "edit",
        "crop",
        {"clip_id": "clip-1", "crop_start_s": 8.0, "crop_end_s": 40.0, "title": "cut"},
    )
    _, path = mock_client.api_call.await_args.args
    body = mock_client.api_call.await_args.kwargs["json"]
    assert path == "/api/edit/crop/clip-1/"
    assert body["crop_start_s"] == 8.0 and body["crop_end_s"] == 40.0
    assert body["is_crop_remove"] is False
    assert body["ui_surface"] == "song_actions"
    assert out["generation_id"] == "clip-cropped"


async def test_fade_requires_times(web: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="fade_in_time"):
        await web.write("edit", "fade", {"clip_id": "clip-1"})


async def test_reverse_body_and_poll_key(web: SunoAdapter, mock_client: AsyncMock) -> None:
    mock_client.api_call.return_value = {"id": "rev-1"}
    out = await web.write("edit", "reverse", {"clip_id": "clip-1", "title": "rev"})
    assert mock_client.api_call.await_args.args[1] == "/api/clips/reverse-clip/"
    assert mock_client.api_call.await_args.kwargs["json"] == {"clip_id": "clip-1", "title": "rev"}
    assert out["generation_id"] == "rev-1"


async def test_remaster_optional_controls(web: SunoAdapter, mock_client: AsyncMock) -> None:
    mock_client.api_call.return_value = {"clips": [{"id": "up-1"}]}
    await web.write("remaster", "create", {"clip_id": "clip-1", "clarity": 0.8, "tags": "techno"})
    body = mock_client.api_call.await_args.kwargs["json"]
    assert mock_client.api_call.await_args.args[1] == "/api/generate/upsample"
    assert body["clip_id"] == "clip-1" and body["clarity"] == 0.8 and body["tags"] == "techno"


async def test_persona_create_requires_name_description(web: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="description"):
        await web.write("persona", "create", {"name": "Sber Persona"})


async def test_playlist_create_and_add(web: SunoAdapter, mock_client: AsyncMock) -> None:
    mock_client.api_call.return_value = {"id": "pl-1"}
    await web.write("playlist", "create", {"name": "DJ Assets"})
    assert mock_client.api_call.await_args.kwargs["json"] == {"name": "DJ Assets"}
    await web.write("playlist", "add_tracks", {"playlist_id": "pl-1", "clip_ids": ["a", "b"]})
    _, path = mock_client.api_call.await_args.args
    assert path == "/api/playlist/v2/pl-1/tracks/add"
    assert mock_client.api_call.await_args.kwargs["json"] == {"clip_ids": ["a", "b"]}


async def test_sample_pack_no_body(web: SunoAdapter, mock_client: AsyncMock) -> None:
    await web.write("stem", "sample_pack", {"clip_id": "clip-1"})
    assert mock_client.api_call.await_args.args[1] == "/api/generate/clip-1/generate_sample_pack"


async def test_clip_read_kinds(web: SunoAdapter, mock_client: AsyncMock) -> None:
    mock_client.api_call.return_value = {"downbeats": [1, 2, 3]}
    out = await web.read("clip", "clip-1", {"kind": "downbeats"})
    assert mock_client.api_call.await_args.args == ("GET", "/api/gen/clip-1/downbeats")
    assert out["kind"] == "downbeats"
    await web.read("clip", "clip-1", {})  # default kind=info
    assert mock_client.api_call.await_args.args[1] == "/api/clip/clip-1"
    await web.read("clip", "clip-1", {"kind": "stems"})
    assert mock_client.api_call.await_args.args[1] == "/api/clip/clip-1/stems"


async def test_clip_read_unknown_kind(web: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="unknown suno clip read kind"):
        await web.read("clip", "clip-1", {"kind": "nope"})


async def test_persona_list_read(web: SunoAdapter, mock_client: AsyncMock) -> None:
    mock_client.api_call.return_value = {"personas": []}
    out = await web.read("persona", None, {})
    assert mock_client.api_call.await_args.args[1] == "/api/persona/get-personas/"
    assert out["kind"] == "list"


async def test_lyrics_read_by_id(web: SunoAdapter, mock_client: AsyncMock) -> None:
    mock_client.api_call.return_value = {"id": "ly-1", "status": "complete"}
    out = await web.read("lyrics", "ly-1", {})
    assert mock_client.api_call.await_args.args[1] == "/api/generate/lyrics/ly-1"
    assert out["task_id"] == "ly-1"


async def test_web_unknown_op(web: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="unknown suno web operation"):
        await web.write("generation", "nonexistent", {})
