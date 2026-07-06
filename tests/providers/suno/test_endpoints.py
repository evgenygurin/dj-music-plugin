"""Tests for the declarative sunoapi.org endpoint registry."""

from __future__ import annotations

from app.providers.suno import endpoints as ep


def test_camel_to_snake_handles_trailing_and_numeric() -> None:
    assert ep.camel_to_snake("audioId") == "audio_id"
    assert ep.camel_to_snake("infillStartS") == "infill_start_s"
    assert ep.camel_to_snake("base64Data") == "base64_data"
    assert ep.camel_to_snake("uploadUrlList") == "upload_url_list"


def test_pull_field_prefers_camel_then_snake_then_alias() -> None:
    assert ep.pull_field({"audioId": "a"}, "audioId") == "a"
    assert ep.pull_field({"audio_id": "a"}, "audioId") == "a"
    # explicit alias: callBackUrl <- callback_url (naive snake is call_back_url)
    assert ep.pull_field({"callback_url": "http://x"}, "callBackUrl") == "http://x"
    assert ep.pull_field({}, "audioId") is None


def test_sunoapi_operations_cover_generation_variants() -> None:
    ops = ep.sunoapi_operations()
    assert ops["generation"][:3] == ("create", "cancel", "download")
    for variant in ("extend", "upload_cover", "add_instrumental", "mashup", "replace_section"):
        assert variant in ops["generation"]
    assert ops["voice"] == ("validate", "generate", "regenerate", "check")
    assert set(ops["file"]) == {"upload_base64", "upload_url", "upload_stream"}


def test_sunoapi_entities_include_all_task_families() -> None:
    ents = ep.sunoapi_entities()
    for entity in (
        "generation",
        "lyrics",
        "wav",
        "vocal_removal",
        "midi",
        "video",
        "cover",
        "persona",
        "style",
        "voice",
        "file",
        "account",
    ):
        assert entity in ents


def test_read_registry_paths_match_docs() -> None:
    assert ep.READ["wav"].path == "/api/v1/wav/record-info"
    assert ep.READ["vocal_removal"].path == "/api/v1/vocal-removal/record-info"
    assert ep.READ["video"].path == "/api/v1/mp4/record-info"
    assert ep.READ["cover"].path == "/api/v1/suno/cover/record-info"
    assert ep.VOICE_VALIDATE_READ.path == "/api/v1/voice/validate-info"
