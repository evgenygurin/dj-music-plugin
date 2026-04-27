"""Entity + provider schema introspection resources.

URIs:
    schema://entities
    schema://entities/{entity}
    schema://providers
    schema://providers/{name}
"""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.registry.entity import EntityRegistry
from app.registry.provider import ProviderRegistry
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.schemas.resource_views import (
    SchemaEntityView,
    SchemaIndexView,
    SchemaProviderIndexView,
    SchemaProviderView,
)
from app.server.di import get_provider_registry


@resource(
    "schema://entities",
    mime_type="application/json",
    tags={"core", "namespace:introspection", "view:schema_index"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def schema_entities_index() -> str:
    """Index of all entities registered in ``EntityRegistry``."""
    return SchemaIndexView(entities=EntityRegistry.names()).model_dump_json()


@resource(
    "schema://entities/{entity}",
    mime_type="application/json",
    tags={"core", "namespace:introspection", "view:schema_entity"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def schema_entities_one(entity: str) -> str:
    """Full schema for one entity — ops, presets, filterable fields, JSON Schemas.

    Raises ``NotFoundError`` (from ``EntityRegistry.get``) on unknown name.
    """
    config = EntityRegistry.get(entity)
    presets: dict[str, list[str]] = {}
    for key, val in config.field_presets.items():
        presets[key] = ["*"] if val == "*" else list(val)
    view = SchemaEntityView(
        name=config.name,
        operations=sorted(config.allowed_ops),
        presets=presets,
        default_preset=config.default_preset,
        searchable_fields=list(config.searchable_fields),
        filterable_fields={k: list(v) for k, v in config.filterable_fields.items()},
        sortable_fields=list(config.sortable_fields),
        relations=list(config.relations.keys()),
        view_schema=config.view_schema.model_json_schema(),
        filter_schema=config.filter_schema.model_json_schema(),
        create_schema=config.create_schema.model_json_schema(),
        update_schema=config.update_schema.model_json_schema(),
    )
    return view.model_dump_json()


@resource(
    "schema://providers",
    mime_type="application/json",
    tags={"core", "namespace:introspection", "view:provider_index"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def schema_providers_index(
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> str:
    """Index of registered providers."""
    return SchemaProviderIndexView(providers=registry.names()).model_dump_json()


@resource(
    "schema://providers/{name}",
    mime_type="application/json",
    tags={"core", "namespace:introspection", "view:provider"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def schema_provider_one(
    name: str,
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> str:
    """Full provider schema. Raises ``NotFoundError`` via registry.get."""
    adapter = registry.get(name)
    # Adapters declare ``entities_supported`` as a ClassVar/property; the
    # fallback is an empty tuple to avoid the audit-class bug where the
    # hardcoded default lied about real surface area (``track_batch``,
    # ``track_similar``, ``artist_tracks``, ``playlist_list``, ``dislikes``
    # were all silently absent from the introspection answer).
    entities_supported = list(getattr(adapter, "entities_supported", ()))
    operations: dict[str, bool] = {
        "read": hasattr(adapter, "read"),
        "write": hasattr(adapter, "write"),
        "search": hasattr(adapter, "search"),
        "download_audio": hasattr(adapter, "download_audio"),
    }
    return SchemaProviderView(
        name=name,
        entities_supported=entities_supported,
        operations=operations,
    ).model_dump_json()
