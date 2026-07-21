from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.domain.render.models import STEM_ORDER
from app.handlers._context_log import safe_info
from app.models.audio_file import DjLibraryItem


def _stem_type_from_path(path: str) -> str | None:
    name = Path(path).name.lower()
    for stem in STEM_ORDER:
        if name.endswith(f"-{stem}.m4a") or name.endswith(f"-{stem}.mp3"):
            return stem
    return None


class StemResolver:
    async def resolve(
        self,
        ctx: Any,
        uow: Any,
        inputs: list[Any],
    ) -> dict[int, dict[str, str]] | None:
        if not inputs:
            return None

        session = getattr(uow, "session", None)
        if session is None:
            return None

        track_ids = [ti.track_id for ti in inputs]
        stmt = select(DjLibraryItem.track_id, DjLibraryItem.file_path).where(
            DjLibraryItem.track_id.in_(track_ids)
        )
        rows = (await session.execute(stmt)).all()
        by_track: dict[int, dict[str, str]] = {tid: {} for tid in track_ids}
        for row in rows:
            stem = _stem_type_from_path(row.file_path)
            if stem is not None:
                by_track[row.track_id][stem] = row.file_path

        required = set(STEM_ORDER)
        missing = {
            tid: sorted(required - set(stems))
            for tid, stems in by_track.items()
            if required - set(stems)
        }
        if missing:
            await safe_info(
                ctx,
                "prepared stem render unavailable; missing stems for "
                f"{len(missing)}/{len(track_ids)} tracks",
            )
            return None

        await safe_info(
            ctx,
            f"prepared stem render: loaded {len(by_track)} x {len(STEM_ORDER)} stems",
        )
        return by_track
