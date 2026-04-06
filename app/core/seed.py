"""Database seed — re-export shim.

The real implementation lives in app.infrastructure.seed.
"""

from app.infrastructure.seed import seed_reference_data

__all__ = ["seed_reference_data"]
