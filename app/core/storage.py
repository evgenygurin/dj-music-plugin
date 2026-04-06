"""Storage backend factory — re-export shim.

The real implementation lives in app.infrastructure.storage.
"""

from app.infrastructure.storage import create_storage_backend, create_transition_cache_backend

__all__ = ["create_storage_backend", "create_transition_cache_backend"]
