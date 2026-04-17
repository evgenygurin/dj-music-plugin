def test_health_ok(rest_client) -> None:
    response = rest_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mcp_ready"] is True
    assert body["tool_count"] == 1
