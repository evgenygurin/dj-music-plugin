from __future__ import annotations

from scripts.fastmcp_json import extract_payload


def test_extracts_tool_structured_content() -> None:
    raw = {
        "content": [{"type": "text", "text": '{"value": 1}'}],
        "structured_content": {"value": 1},
    }

    assert extract_payload(raw) == {"value": 1}


def test_extracts_resource_list_text_json() -> None:
    raw = [
        {
            "uri": "reference://templates",
            "mimeType": "text/plain",
            "text": '{"total": 8, "templates": [{"name": "roller_90"}]}',
        }
    ]

    assert extract_payload(raw) == {"total": 8, "templates": [{"name": "roller_90"}]}


def test_extracts_dict_content_text_json_without_structured_content() -> None:
    raw = {"content": [{"type": "text", "text": '{"set_id": 99}'}]}

    assert extract_payload(raw) == {"set_id": 99}


def test_preserves_non_json_resource_text() -> None:
    raw = [{"uri": "local://plain", "text": "not-json"}]

    assert extract_payload(raw) == "not-json"
