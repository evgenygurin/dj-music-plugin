"""Template Method for batch-processing handlers (GoF: Template Method).

Eliminates the duplicated loop/progress/error/skip pattern across handlers.
Subclasses override ``process_one``; the base provides the loop skeleton.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from fastmcp.server.context import Context

from app.handlers._context_log import safe_info, safe_report_progress
from app.repositories.unit_of_work import UnitOfWork

T = TypeVar("T")


class BaseBatchHandler(ABC, Generic[T]):
    """Template Method for processing a batch of items.

    Usage:
      class MyHandler(BaseBatchHandler[int]):
          async def process_one(self, ctx, uow, item_id, data, **deps) -> dict[str, Any]:
              ...

      result = await MyHandler().run(ctx, uow, data)
    """

    @abstractmethod
    def parse_ids(self, data: dict[str, Any]) -> list[T]:
        """Extract item IDs from request data."""

    @abstractmethod
    async def process_one(
        self,
        ctx: Context,
        uow: UnitOfWork,
        item_id: T,
        data: dict[str, Any],
        *,
        index: int = 0,
        **deps: Any,
    ) -> dict[str, Any]:
        """Process a single item. Return the item's result dict. Raise on error.

        ``index`` is the 0-based position in the batch — useful for handlers
        that number output files sequentially.
        """
        ...

    def success_key(self) -> str:
        """Response key for successful items (default: ``"processed"``)."""
        return "processed"

    def summary_message(self, *, ok: int, skipped: int, errors: int) -> str:
        return f"{type(self).__name__}: {ok} ok, {skipped} skipped, {errors} errors"

    async def run(
        self,
        ctx: Context,
        uow: UnitOfWork,
        data: dict[str, Any],
        **deps: Any,
    ) -> dict[str, Any]:
        ids = self.parse_ids(data)
        total = len(ids)

        successes: list[dict[str, Any]] = []
        skips: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for i, item_id in enumerate(ids):
            skip = await self._pre_check(uow, item_id, data, **deps)
            if skip is not None:
                skips.append(skip)
                await safe_report_progress(ctx, progress=i + 1, total=total)
                continue

            try:
                result = await self.process_one(
                    ctx, uow, item_id, data, index=i, total=total, **deps
                )
                successes.append({"id": item_id, **result})
            except Exception as exc:
                errors.append({"id": item_id, "error": str(exc)})

            await safe_report_progress(ctx, progress=i + 1, total=total)

        await safe_info(
            ctx,
            self.summary_message(ok=len(successes), skipped=len(skips), errors=len(errors)),
        )

        return {
            self.success_key(): successes,
            "skipped": skips,
            "errors": errors,
        }

    async def _pre_check(
        self, uow: UnitOfWork, item_id: T, data: dict[str, Any], **deps: Any
    ) -> dict[str, Any] | None:
        """Return a skip dict to skip, or None to process.

        Override in subclass for custom skip logic. Default: no skip.
        """
        return None
