"""EntityRegistry tests."""

from collections.abc import Mapping

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.registry.entity import EntityConfig, EntityRegistry
from app.shared.errors import NotFoundError


class _Base(DeclarativeBase):
    pass


class _WidgetModel(_Base):
    __tablename__ = "_widgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class WidgetView(BaseModel):
    id: int
    name: str


class WidgetFilter(BaseModel):
    id: int | None = None


class WidgetCreate(BaseModel):
    name: str


class WidgetUpdate(BaseModel):
    name: str | None = None


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    EntityRegistry._registry.clear()  # type: ignore[attr-defined]


def _make_config(**overrides: object) -> EntityConfig:
    base: Mapping[str, object] = {
        "name": "widget",
        "model": _WidgetModel,
        "repo_attr": "widgets",
        "view_schema": WidgetView,
        "filter_schema": WidgetFilter,
        "create_schema": WidgetCreate,
        "update_schema": WidgetUpdate,
        "allowed_ops": frozenset({"list", "get", "create"}),
        "field_presets": {"id": ["id"], "full": "*"},
        "default_preset": "id",
        "searchable_fields": ("name",),
        "filterable_fields": {"id": ("eq", "in")},
        "sortable_fields": ("id", "name"),
        "relations": {},
        "tags": frozenset({"namespace:test"}),
    }
    return EntityConfig(**{**base, **overrides})  # type: ignore[arg-type]


def test_register_and_get() -> None:
    cfg = _make_config()
    EntityRegistry.register(cfg)
    assert EntityRegistry.get("widget") is cfg


def test_get_unknown_raises_not_found() -> None:
    with pytest.raises(NotFoundError) as exc_info:
        EntityRegistry.get("bogus")
    assert "bogus" in str(exc_info.value)


def test_names_returns_sorted_list() -> None:
    EntityRegistry.register(_make_config(name="zebra"))
    EntityRegistry.register(_make_config(name="alpha"))
    assert EntityRegistry.names() == ["alpha", "zebra"]


def test_register_duplicate_raises() -> None:
    EntityRegistry.register(_make_config())
    with pytest.raises(ValueError) as exc_info:
        EntityRegistry.register(_make_config())
    assert "widget" in str(exc_info.value)


def test_config_is_frozen() -> None:
    cfg = _make_config()
    with pytest.raises(Exception):
        cfg.name = "other"  # type: ignore[misc]


def test_allowed_ops_validation() -> None:
    cfg = _make_config()
    assert "list" in cfg.allowed_ops
    assert "delete" not in cfg.allowed_ops


def test_has_handler_flags() -> None:
    cfg_default = _make_config()
    assert cfg_default.create_handler is None

    async def fake_handler(ctx, uow, data):  # type: ignore[no-untyped-def]
        return {}

    cfg_custom = _make_config(create_handler=fake_handler)
    assert cfg_custom.create_handler is fake_handler
