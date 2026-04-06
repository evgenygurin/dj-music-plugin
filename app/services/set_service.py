"""Set service — re-export shim for backward compatibility.

The real implementation lives in app.services.set.facade.
"""

from app.services.set.facade import SetService

__all__ = ["SetService"]
