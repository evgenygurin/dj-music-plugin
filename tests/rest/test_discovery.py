def test_list_tools(rest_client) -> None:
    response = rest_client.get("/api/tools")
    assert response.status_code == 200
    assert response.json() == [{"name": "entity_list", "description": "list", "tags": ["core"]}]


def test_list_tools_filter_by_tag(rest_client) -> None:
    r = rest_client.get("/api/tools?tag=no-such")
    assert r.status_code == 200
    assert r.json() == []


def test_get_tool(rest_client) -> None:
    response = rest_client.get("/api/tools/entity_list")
    assert response.status_code == 200
    assert response.json()["name"] == "entity_list"
