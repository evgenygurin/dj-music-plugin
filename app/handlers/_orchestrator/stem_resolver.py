from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.domain.render.models import STEM_ORDER
from app.handlers._context_log import safe_info
from app.models.audio_file import DjLibraryItem

_STEM_EXTENSIONS = (".m4a", ".mp3", ".wav", ".flac")
_STEM_ALIASES: dict[str, tuple[str, ...]] = {
    **{stem: (stem,) for stem in STEM_ORDER},
    "vocals": ("acappella",),
    "other": ("harmonic", "instrumental"),
}


def _stem_type_from_path(path: str) -> tuple[str, ...]:
    name = Path(path).name.lower()
    for stem_name, internal_stems in _STEM_ALIASES.items():
        for ext in _STEM_EXTENSIONS:
            suffix = f"{stem_name}{ext}"
            if name == suffix or name.endswith(f"-{suffix}"):
                return internal_stems
    return ()


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
            for stem in _stem_type_from_path(row.file_path):
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
