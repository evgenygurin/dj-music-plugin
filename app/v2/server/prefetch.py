"""Speculative prefetch helper.

Used by ``suggest_next_track`` (Phase 4 resource) to warm the top-N
candidates in the background: run L3 analysis if missing, then
pre-compute and cache the transition score. The next
``suggest_next_track`` call against the same track is served from cache.

Best-effort only — every error is swallowed. Never blocks the caller.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.v2.config.discovery import DiscoverySettings

log = logging.getLogger(__name__)

AnalyzeHandler = Callable[..., Awaitable[Any]]
Scorer = Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class SpeculativePrefetch:
    """Pre-warm top-N candidate scores + analysis levels for one track."""

    uow: Any
    scorer: Scorer
    settings: DiscoverySettings
    analyze_handler: AnalyzeHandler | None = None

    async def warm(self, *, from_track_id: int, candidate_ids: list[int]) -> None:
        """Spend at most ``settings.prefetch_top_n`` scoring calls + at most
        ``settings.prefetch_max_l3`` analysis upgrades warming the top candidates.
        """
        top_n = max(0, self.settings.prefetch_top_n)
        if top_n == 0 or not candidate_ids:
            return

        targets = candidate_ids[:top_n]
        try:
            await self._ensure_level(targets)
            for to_track_id in targets:
                try:
                    await self.scorer(from_track_id, to_track_id)
                except Exception as exc:
                    log.debug(
                        "prefetch score failed",
                        extra={"from": from_track_id, "to": to_track_id, "err": str(exc)},
                    )
        except Exception as exc:
            log.debug("prefetch aborted", extra={"err": str(exc)})

    async def _ensure_level(self, track_ids: list[int]) -> None:
        """Trigger analyze_handler for tracks below L3, bounded by prefetch_max_l3."""
        if self.analyze_handler is None:
            return

        budget = max(0, self.settings.prefetch_max_l3)
        if budget == 0:
            return

        needs_upgrade: list[int] = []
        for tid in track_ids:
            try:
                level = await self.uow.track_features.get_analysis_level(tid)
            except Exception:
                continue
            if level < 3:
                needs_upgrade.append(tid)
            if len(needs_upgrade) >= budget:
                break

        if not needs_upgrade:
            return

        try:
            await self.analyze_handler(track_ids=needs_upgrade, level=3)
        except Exception as exc:
            log.debug("prefetch analyze failed", extra={"err": str(exc), "ids": needs_upgrade})
