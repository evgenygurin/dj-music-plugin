"""Curation service — re-export shim for backward compatibility.

The real implementation lives in app.services.curation.facade.
"""

from app.services.curation.facade import CurationService

__all__ = ["CurationService"]
