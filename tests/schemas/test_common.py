"""EntityListView + EntityAggregateView + EntityRef."""

from app.schemas.common import EntityAggregateView, EntityListView, EntityRef


def test_entity_ref() -> None:
    r = EntityRef(entity="track", id=42)
    assert r.entity == "track"
    assert r.id == 42


def test_entity_list_view() -> None:
    v = EntityListView(
        items=[{"id": 1}, {"id": 2}],
        next_cursor="abc",
        total=2,
        preset="id",
        fields=["id"],
    )
    assert v.has_more is True
    assert len(v.items) == 2


def test_entity_list_view_no_more() -> None:
    v = EntityListView(items=[{"id": 1}], next_cursor=None, total=None, fields=["id"])
    assert v.has_more is False


def test_entity_aggregate_view_scalar() -> None:
    v = EntityAggregateView(operation="count", value=42)
    assert v.value == 42


def test_entity_aggregate_view_groups() -> None:
    v = EntityAggregateView(operation="group_by", groups={"peak_time": 120, "acid": 42})
    assert v.groups == {"peak_time": 120, "acid": 42}
