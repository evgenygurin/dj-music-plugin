"""v2 ORM models. One aggregate root per module.

Import side-effect: all model classes are registered on ``Base.metadata``.
"""

from app.v2.models.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
