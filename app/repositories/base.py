"""Generic async repository with CRUD and cursor pagination."""

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.pagination import CursorPage, decode_cursor, encode_cursor

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base repository providing CRUD operations and cursor-based pagination.

    Subclasses specify the SQLAlchemy model via ``model_class``.
    All mutations use ``session.flush()`` — never ``commit()``.
    """

    def __init__(self, session: AsyncSession, model_class: type[T]) -> None:
        self.session = session
        self.model_class = model_class

    async def get_by_id(self, id: int) -> T | None:
        """Return a single instance by primary key, or ``None``."""
        stmt = select(self.model_class).where(self.model_class.id == id)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 20, cursor: str | None = None) -> CursorPage[T]:
        """Return a page of instances ordered by id with cursor pagination."""
        return await self._paginate(
            select(self.model_class),
            limit=limit,
            cursor=cursor,
        )

    async def create(self, instance: T) -> T:
        """Add an instance to the session and flush to obtain its id."""
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: T) -> T:
        """Flush pending changes for the given instance."""
        await self.session.flush()
        return instance

    async def delete(self, id: int) -> bool:
        """Delete an instance by id. Returns ``True`` if found and deleted."""
        instance = await self.get_by_id(id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True

    # ── Pagination helper ────────────────────────────────

    async def _paginate(
        self,
        stmt: Any,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[T]:
        """Apply cursor-based pagination to a select statement.

        Assumes the model has an ``id`` column used for ordering.
        """
        id_col = self.model_class.id  # type: ignore[attr-defined]

        # Total count (without cursor filter)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        # Apply cursor filter
        if cursor is not None:
            last_id = decode_cursor(cursor)
            stmt = stmt.where(id_col > last_id)

        stmt = stmt.order_by(id_col).limit(limit)
        result = await self.session.execute(stmt)
        items: list[T] = list(result.scalars().all())

        next_cursor: str | None = None
        if items and len(items) == limit:
            last_item = items[-1]
            next_cursor = encode_cursor(last_item.id)  # type: ignore[attr-defined]

        return CursorPage(items=items, next_cursor=next_cursor, total=total)
