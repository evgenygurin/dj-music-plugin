"""Regression tests for the FastAPI wrapper."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.server import api
from app.api.state import build_api_runtime
from app.api.tool_registry import ToolRegistry
from app.server import mcp


class _FakeContent:
    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload

    def model_dump(self, exclude_none: bool = True) -> dict[str, str]:
        return self._payload


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    runtime = build_api_runtime(mcp)
    api.state.runtime = runtime

    class _FakeYmClient:
        async def close(self) -> None:
            return None

    @asynccontextmanager
    async def _fake_mcp_lifespan(_app):
        yield

    monkeypatch.setattr(runtime.mcp_app.router, "lifespan_context", _fake_mcp_lifespan)
    monkeypatch.setattr("app.api.lifespan.build_ym_client", lambda: _FakeYmClient())

    with TestClient(api) as client:
        yield client, runtime


def test_health_endpoint_reports_runtime_state(api_client) -> None:
    client, runtime = api_client

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "tools_discovered": len(runtime.tool_registry.tools),
        "mcp_ready": True,
    }


def test_discovery_endpoints_preserve_tool_metadata(api_client) -> None:
    client, runtime = api_client
    first_tool = runtime.tool_registry.tools[0]

    list_response = client.get("/api/tools")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == len(runtime.tool_registry.tools)

    detail_response = client.get(f"/api/tools/{first_tool['name']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == first_tool["name"]

    schema_response = client.get(f"/api/tools/{first_tool['name']}/schema")
    assert schema_response.status_code == 200
    assert schema_response.json() == first_tool["input_schema"]


def test_call_tool_returns_503_when_mcp_not_ready(api_client) -> None:
    client, runtime = api_client
    runtime.mcp_ready = False
    runtime.tool_registry = ToolRegistry(
        tools=[
            {
                "name": "fake_tool",
                "description": "Fake",
                "tags": [],
                "annotations": None,
                "input_schema": {"type": "object"},
                "timeout": None,
            }
        ]
    )

    response = client.post("/api/tools/fake_tool/call", json={"arguments": {}})

    assert response.status_code == 503
    assert "DB may be unreachable" in response.text


def test_call_tool_executes_and_preserves_response_shape(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime = api_client
    runtime.tool_registry = ToolRegistry(
        tools=[
            {
                "name": "fake_tool",
                "description": "Fake",
                "tags": [],
                "annotations": None,
                "input_schema": {"type": "object"},
                "timeout": None,
            }
        ]
    )
    monkeypatch.setattr(
        runtime.mcp,
        "call_tool",
        AsyncMock(
            return_value=SimpleNamespace(
                content=[_FakeContent({"type": "text", "text": "ok"})],
                structured_content={"status": "ok"},
            )
        ),
    )

    response = client.post("/api/tools/fake_tool/call", json={"arguments": {"limit": 1}})

    assert response.status_code == 200
    assert response.json() == {
        "tool_name": "fake_tool",
        "content": [{"type": "text", "text": "ok"}],
        "structured_content": {"status": "ok"},
        "is_error": False,
    }


def test_openapi_keeps_critical_routes_and_examples(api_client) -> None:
    client, _runtime = api_client

    response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    assert payload["info"]["version"]  # non-empty version string
    assert "/api/health" in payload["paths"]
    assert "/api/tools" in payload["paths"]
    assert "/api/tools/{tool_name}/call" in payload["paths"]
    examples = payload["paths"]["/api/tools/{tool_name}/call"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]
    assert "commit_set_version" in examples
    assert examples["commit_set_version"]["value"]["arguments"]["name"] == "Peak Hour 60"


def test_mcp_mount_is_present(api_client) -> None:
    client, _runtime = api_client
    del client

    assert any(getattr(route, "path", None) == "/mcp" for route in api.routes)
