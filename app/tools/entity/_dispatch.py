"""Shared helper for routing entity CRUD handlers to the right service.

Handlers have different 4th-positional-argument dependencies:

    | Handler                          | 4th param name |
    | ``audio_file_download_handler``  | ``registry``   |
    | ``track_import_handler``         | ``registry``   |
    | ``set_version_build_handler``    | ``_registry``  |
    | ``track_features_analyze``       | ``pipeline``   |
    | ``track_features_reanalyze``     | ``pipeline``   |
    | ``transition_persist``           | ``scorer``     |

The dispatchers (``entity_create`` / ``entity_update``) previously always passed
``ProviderRegistry`` as the 4th argument, which silently worked for handlers
whose 4th param was ``registry`` but broke at runtime for handlers expecting
``pipeline`` or ``scorer`` (``AttributeError`` on the first service call).

``call_handler`` inspects the handler signature and forwards the matching
service. Handlers themselves stay unchanged.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

_SERVICE_PARAMS = frozenset({"registry", "_registry", "pipeline", "scorer"})


async def call_handler(
    handler: Callable[..., Awaitable[Any]],
    *,
    ctx: Any,
    uow: Any,
    data: dict[str, Any],
    registry: Any,
    pipeline: Any,
    scorer: Any,
) -> Any:
    """Invoke ``handler(ctx, uow, data, <service>)`` picking ``<service>`` by
    the 4th-parameter name on the handler.

    Handlers without a 4th parameter are called with three arguments.
    Unknown 4th-parameter names fall back to the ProviderRegistry for
    backward compatibility.
    """
    sig = inspect.signature(handler)
    params = list(sig.parameters.keys())
    if len(params) < 4:
        return await handler(ctx, uow, data)

    service_map: dict[str, Any] = {
        "registry": registry,
        "_registry": registry,
        "provider_registry": registry,
        "pipeline": pipeline,
        "scorer": scorer,
    }

    name = params[3]
    if name in service_map:
        # Forward the primary 4th-positional service, plus any FURTHER service
        # params the handler declares (5th+, by name) as keyword args. This
        # lets a handler ask for two services — e.g. ``track_features_analyze``
        # takes ``pipeline`` AND an optional ``registry`` for Beatport
        # enrichment — without breaking single-service handlers.
        extra = {p: service_map[p] for p in params[4:] if p in service_map}
        return await handler(ctx, uow, data, service_map[name], **extra)

    # Unknown name — legacy fallback to registry keeps existing handlers alive.
    return await handler(ctx, uow, data, registry)
