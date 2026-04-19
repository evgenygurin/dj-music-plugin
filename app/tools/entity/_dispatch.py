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

    name = params[3]
    if name in _SERVICE_PARAMS:
        service_map: dict[str, Any] = {
            "registry": registry,
            "_registry": registry,
            "pipeline": pipeline,
            "scorer": scorer,
        }
        return await handler(ctx, uow, data, service_map[name])

    # Unknown name — legacy fallback to registry keeps existing handlers alive.
    return await handler(ctx, uow, data, registry)
