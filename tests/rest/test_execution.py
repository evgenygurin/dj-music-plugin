from unittest.mock import AsyncMock


def test_call_tool_returns_structured_content(rest_client) -> None:
    response = rest_client.post(
        "/api/tools/entity_list/call",
        json={"arguments": {"entity": "track"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_error"] is False
    assert body["result"] == {"items": [1, 2]}


def test_call_tool_error_path(rest_client, mock_mcp) -> None:
    mock_mcp.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
    response = rest_client.post(
        "/api/tools/entity_list/call",
        json={"arguments": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_error"] is True
    assert "boom" in body["error"]
