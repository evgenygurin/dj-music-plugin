"""EntityRegistry — declarative configuration for generic CRUD tools.

Per blueprint §5. An EntityConfig maps an entity name (e.g. "track") to:
- ORM model + repository attribute on UnitOfWork
- Pydantic schemas (View, Filter, Create, Update)
- Allowed operations + visibility tags
- Field presets for projection, searchable/filterable/sortable fields
- Relations that can be ``include_relations`` ed
- Optional custom handlers for create/update/delete (side-effects)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel

from app.shared.errors import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase

# Handler signature: (ctx, uow, data) -> view-dict(s)
HandlerCallable = Callable[
    [Any, Any, dict[str, Any]],
    Awaitable[dict[str, Any] | list[dict[str, Any]]],
]

Operation = Literal["list", "get", "create", "update", "delete", "aggregate"]
_FieldPreset = Sequence[str] | Literal["*"]


@dataclass(frozen=True, slots=True)
class EntityConfig:
    """Declarative entity configuration. All fields required except handlers."""

    name: str
    model: type[DeclarativeBase]
    repo_attr: str
    view_schema: type[BaseModel]
    filter_schema: type[BaseModel]
    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    allowed_ops: frozenset[Operation]
    field_presets: Mapping[str, _FieldPreset]
    default_preset: str
    searchable_fields: Sequence[str]
    filterable_fields: Mapping[str, Sequence[str]]
    sortable_fields: Sequence[str]
    relations: Mapping[str, str]
    tags: frozenset[str]

    # Handlers for side-effect CRUD. None → default repo behaviour.
    create_handler: HandlerCallable | None = None
    update_handler: HandlerCallable | None = None
    delete_handler: HandlerCallable | None = None


class EntityRegistry:
    """Process-wide registry of EntityConfig objects, keyed by entity name.

    Registration happens once at server startup (see
    ``app/v2/server/lifespan.py`` in Phase 5). Lookup is O(1).
    """

    _registry: ClassVar[dict[str, EntityConfig]] = {}

    @classmethod
    def register(cls, config: EntityConfig) -> None:
        """Register an EntityConfig. Raises ``ValueError`` on duplicate name."""
        if config.name in cls._registry:
            raise ValueError(f"entity {config.name!r} already registered")
        cls._registry[config.name] = config

    @classmethod
    def get(cls, name: str) -> EntityConfig:
        """Return the config for ``name``. Raises ``NotFoundError`` if unknown."""
        cfg = cls._registry.get(name)
        if cfg is None:
            raise NotFoundError("entity", name)
        return cfg

    @classmethod
    def names(cls) -> list[str]:
        """Return all registered entity names, sorted alphabetically."""
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """Remove all registrations. Intended for tests only."""
        cls._registry.clear()
