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

# Handler signature: (ctx, uow, data, *deps) -> view-dict(s).
# Some handlers take an extra ProviderRegistry / AnalysisPipeline / scorer
# arg injected by the entity dispatcher; ``...`` allows the variation.
HandlerCallable = Callable[
    ...,
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


def resolve_field_projection(
    fields: list[str] | str | None,
    config: EntityConfig,
) -> set[str] | None:
    """Resolve the ``fields`` parameter from ``entity_list`` / ``entity_get``.

    Returns the set of field names to keep on the response, or ``None`` to
    indicate "all fields" (full projection).

    Accepts:

    - ``None`` → fall back to ``config.default_preset``.
    - ``str`` → preset name (``"id"`` / ``"ref"`` / ``"summary"`` / ``"full"``)
      OR a JSON-encoded list (``'["id", "title"]'``)
      OR a comma-separated list (``"id,title"``).
    - ``list[str]`` → use directly.

    The ``"full"`` preset (or any preset with value ``"*"``) returns ``None``
    so callers know to skip projection entirely. Empty input also returns
    ``None`` (defensive: don't return an empty dict from a typo).

    Regression: prior to v1.0.13 the parameter was accepted in the tool
    signature but never applied — every response returned the full row
    regardless of what the caller asked for.
    """
    import json

    presets = config.field_presets
    default = config.default_preset

    # 1. Normalise to ``list[str]`` (or signal "full" via ``None``).
    if fields is None:
        fields = default

    if isinstance(fields, str):
        s = fields.strip()
        if not s:
            return None
        # Preset name?
        if s in presets:
            preset_val = presets[s]
            if preset_val == "*":
                return None
            return set(preset_val)
        # JSON-encoded list (Claude Code stdio shim stringifies list args).
        if s.startswith("["):
            try:
                parsed = json.loads(s)
            except json.JSONDecodeError:
                # Fall through to CSV; "[" without valid JSON is unusual but
                # we don't want to crash the dispatcher on a typo.
                parsed = None
            if isinstance(parsed, list):
                return {str(x) for x in parsed if str(x).strip()}
        # CSV fallback ("id,title" or single field "id").
        parts = {p.strip() for p in s.split(",") if p.strip()}
        return parts or None

    # ``list[str]``: filter empties so an accidental ``[""]`` doesn't break
    # ``model_dump(include={...})``.
    cleaned = {str(x) for x in fields if str(x).strip()}
    return cleaned or None
