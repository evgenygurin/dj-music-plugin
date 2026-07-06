"""SunoAdapter tests for the full sunoapi.org (api_key) surface — no network."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.providers.suno.adapter import SunoAdapter
from app.shared.errors import ValidationError


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.api_call.return_value = {"taskId": "task-1", "status": "PENDING"}
    client.upload_file.return_value = {"downloadUrl": "https://cdn.example/up.mp3"}
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> SunoAdapter:
    return SunoAdapter(client=mock_client, default_model="V4_5", payload_mode="sunoapi")


def test_sunoapi_mode_surface_is_expanded(adapter: SunoAdapter) -> None:
    assert "lyrics" in adapter.entities_supported
    assert "voice" in adapter.entities_supported
    assert "file" in adapter.entities_supported
    assert "extend" in adapter.operations_supported["generation"]
    assert adapter.operations_supported["voice"] == (
        "validate",
        "generate",
        "regenerate",
        "check",
    )


async def test_sunoapi_mode_blocks_web_only_ops(mock_client: AsyncMock) -> None:
    # in sunoapi mode, a browser-web-only op (edit.crop) is not in the sunoapi
    # registry and is rejected without a network call.
    api = SunoAdapter(client=mock_client, payload_mode="sunoapi")
    with pytest.raises(ValidationError, match="unknown suno operation"):
        await api.write("edit", "crop", {"clip_id": "x", "crop_start_s": 0, "crop_end_s": 10})


async def test_suno_web_mode_blocks_sunoapi_only_ops(mock_client: AsyncMock) -> None:
    # in suno_web mode, a sunoapi-only op (add_instrumental) is not in the web
    # registry and is rejected.
    web = SunoAdapter(client=mock_client, payload_mode="suno_web")
    assert "edit" in web.entities_supported
    with pytest.raises(ValidationError, match="unknown suno web operation"):
        await web.write("generation", "add_instrumental", {"uploadUrl": "x"})


async def test_extend_builds_body_and_targets_correct_path(
    adapter: SunoAdapter, mock_client: AsyncMock
) -> None:
    out = await adapter.write(
        "generation",
        "extend",
        {
            "audioId": "audio-9",
            "defaultParamFlag": True,
            "continueAt": 45.5,
            "style": ["hypnotic techno", "dub"],
            "model": "V5",
        },
    )
    method, path = mock_client.api_call.await_args.args
    body = mock_client.api_call.await_args.kwargs["json"]
    assert (method, path) == ("POST", "/api/v1/generate/extend")
    assert body["audioId"] == "audio-9"
    assert body["defaultParamFlag"] is True
    assert body["continueAt"] == 45.5
    assert body["style"] == "hypnotic techno, dub"  # list stringified
    assert body["model"] == "V5"
    assert body["callBackUrl"] == ""  # injected default (empty is fine for poll flow)
    assert out["task_id"] == "task-1"


async def test_extend_missing_required_raises(adapter: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="audioId"):
        await adapter.write("generation", "extend", {"defaultParamFlag": True})


async def test_add_instrumental_requires_documented_fields(adapter: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="negativeTags"):
        await adapter.write(
            "generation",
            "add_instrumental",
            {"uploadUrl": "http://x", "title": "t", "tags": "techno"},
        )


async def test_add_instrumental_coerces_model_to_allowed(
    adapter: SunoAdapter, mock_client: AsyncMock
) -> None:
    await adapter.write(
        "generation",
        "add_instrumental",
        {
            "uploadUrl": "http://x",
            "title": "t",
            "negativeTags": "vocals",
            "tags": "techno",
            "model": "V4",  # not allowed for add-instrumental -> coerced to V4_5PLUS
        },
    )
    body = mock_client.api_call.await_args.kwargs["json"]
    assert body["model"] == "V4_5PLUS"


async def test_mashup_keeps_array_field(adapter: SunoAdapter, mock_client: AsyncMock) -> None:
    await adapter.write(
        "generation",
        "mashup",
        {"uploadUrlList": ["http://a", "http://b"], "customMode": False},
    )
    body = mock_client.api_call.await_args.kwargs["json"]
    assert body["uploadUrlList"] == ["http://a", "http://b"]
    assert body["customMode"] is False


async def test_replace_section_full_field_set(
    adapter: SunoAdapter, mock_client: AsyncMock
) -> None:
    await adapter.write(
        "generation",
        "replace_section",
        {
            "taskId": "t",
            "audioId": "a",
            "prompt": "new lyric",
            "tags": "techno",
            "title": "x",
            "fullLyrics": "full",
            "infillStartS": 12.0,
            "infillEndS": 24.0,
        },
    )
    _, path = mock_client.api_call.await_args.args
    assert path == "/api/v1/generate/replace-section"
    body = mock_client.api_call.await_args.kwargs["json"]
    assert body["infillStartS"] == 12.0 and body["infillEndS"] == 24.0


async def test_wav_and_vocal_removal_creates(adapter: SunoAdapter, mock_client: AsyncMock) -> None:
    await adapter.write("wav", "create", {"taskId": "t", "audioId": "a"})
    assert mock_client.api_call.await_args.args[1] == "/api/v1/wav/generate"
    await adapter.write(
        "vocal_removal", "create", {"taskId": "t", "audioId": "a", "type": "split_stem"}
    )
    body = mock_client.api_call.await_args.kwargs["json"]
    assert mock_client.api_call.await_args.args[1] == "/api/v1/vocal-removal/generate"
    assert body["type"] == "split_stem"


async def test_lyrics_create_and_timestamped(adapter: SunoAdapter, mock_client: AsyncMock) -> None:
    await adapter.write("lyrics", "create", {"prompt": "a song about acid"})
    assert mock_client.api_call.await_args.args[1] == "/api/v1/lyrics"
    assert mock_client.api_call.await_args.kwargs["json"]["callBackUrl"] == ""

    await adapter.write("lyrics", "timestamped", {"taskId": "t", "audioId": "a"})
    body = mock_client.api_call.await_args.kwargs["json"]
    assert mock_client.api_call.await_args.args[1] == "/api/v1/generate/get-timestamped-lyrics"
    # timestamped does not inject a callBackUrl (sync-style endpoint)
    assert "callBackUrl" not in body


async def test_style_boost_is_content_only(adapter: SunoAdapter, mock_client: AsyncMock) -> None:
    await adapter.write("style", "boost", {"content": "dark hypnotic techno"})
    body = mock_client.api_call.await_args.kwargs["json"]
    assert mock_client.api_call.await_args.args[1] == "/api/v1/style/generate"
    assert body == {"content": "dark hypnotic techno"}


async def test_voice_validate_and_regenerate(adapter: SunoAdapter, mock_client: AsyncMock) -> None:
    await adapter.write(
        "voice",
        "validate",
        {"voiceUrl": "http://v", "vocalStartS": 1, "vocalEndS": 5},
    )
    assert mock_client.api_call.await_args.args[1] == "/api/v1/voice/validate"

    # the API field is misspelled "calBackUrl" — alias resolves callback_url to it
    await adapter.write("voice", "regenerate", {"taskId": "t", "callback_url": "http://cb"})
    body = mock_client.api_call.await_args.kwargs["json"]
    assert body["calBackUrl"] == "http://cb"


async def test_read_wav_hits_record_info(adapter: SunoAdapter, mock_client: AsyncMock) -> None:
    mock_client.api_call.return_value = {"taskId": "t", "status": "SUCCESS"}
    out = await adapter.read("wav", "t", {})
    method, path = mock_client.api_call.await_args.args
    assert (method, path) == ("GET", "/api/v1/wav/record-info")
    assert mock_client.api_call.await_args.kwargs["params"] == {"taskId": "t"}
    assert out["ready"] is True
    assert out["task_id"] == "t"


async def test_read_voice_validate_kind_switches_endpoint(
    adapter: SunoAdapter, mock_client: AsyncMock
) -> None:
    await adapter.read("voice", "t", {"kind": "validate"})
    assert mock_client.api_call.await_args.args[1] == "/api/v1/voice/validate-info"
    await adapter.read("voice", "t", {})
    assert mock_client.api_call.await_args.args[1] == "/api/v1/voice/record-info"


async def test_read_requires_id_for_task_entities(adapter: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="requires id"):
        await adapter.read("midi", None, {})


async def test_file_upload_base64_and_url(adapter: SunoAdapter, mock_client: AsyncMock) -> None:
    out = await adapter.write(
        "file",
        "upload_base64",
        {"base64Data": "AAAA", "uploadPath": "dj/assets"},
    )
    assert mock_client.upload_file.await_args.args[0] == "/api/file-base64-upload"
    assert out["upload_url"] == "https://cdn.example/up.mp3"

    await adapter.write("file", "upload_url", {"fileUrl": "http://x.mp3", "uploadPath": "dj"})
    assert mock_client.upload_file.await_args.args[0] == "/api/file-url-upload"


async def test_file_upload_stream_reads_local_file(
    adapter: SunoAdapter, mock_client: AsyncMock, tmp_path: Path
) -> None:
    src = tmp_path / "loop.mp3"
    src.write_bytes(b"ID3 fake mp3")
    await adapter.write(
        "file",
        "upload_stream",
        {"local_path": str(src), "uploadPath": "dj/loops", "fileName": "loop.mp3"},
    )
    assert mock_client.upload_file.await_args.args[0] == "/api/file-stream-upload"
    files = mock_client.upload_file.await_args.kwargs["files"]
    assert files["file"][0] == "loop.mp3"
    data = mock_client.upload_file.await_args.kwargs["data"]
    assert data["uploadPath"] == "dj/loops"


async def test_file_upload_stream_missing_local_file(adapter: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="local file not found"):
        await adapter.write(
            "file", "upload_stream", {"local_path": "/nope/x.mp3", "uploadPath": "dj"}
        )


async def test_unknown_operation_lists_supported(adapter: SunoAdapter) -> None:
    with pytest.raises(ValidationError, match="unknown suno operation"):
        await adapter.write("generation", "nonexistent", {})


async def test_account_read_reports_payload_mode(
    adapter: SunoAdapter, mock_client: AsyncMock
) -> None:
    mock_client.get_account.return_value = {"total_credits_left": 100}
    out = await adapter.read("account", None, {})
    assert out["payload_mode"] == "sunoapi"
    assert out["credits_left"] == 100
