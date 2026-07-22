from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.domain.render.models import DEMUCS_STEM_ORDER, STEM_ORDER
from app.handlers._context_log import safe_info
from app.models.audio_file import DjLibraryItem

_STEM_EXTENSIONS = (".m4a", ".mp3", ".wav", ".flac")
_STEM_ALIASES: dict[str, tuple[str, ...]] = {
    **{stem: (stem,) for stem in STEM_ORDER},
    **{stem: (stem,) for stem in DEMUCS_STEM_ORDER},
}


def _stem_type_from_path(path: str) -> tuple[str, ...]:
    name = Path(path).name.lower()
    if Path(name).suffix in _STEM_EXTENSIONS:
        name = Path(name).stem
    for stem_name, internal_stems in _STEM_ALIASES.items():
        if name == stem_name or name.endswith(f"-{stem_name}"):
            return internal_stems
    return ()


def _expand_stem_paths(stems: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, path in stems.items():
        internal_stems = _stem_type_from_path(str(key)) or _stem_type_from_path(str(path))
        for stem in internal_stems:
            result[stem] = str(path)
    return result


def _complete_stem_order(stems: dict[str, str]) -> tuple[str, ...] | None:
    keys = set(stems)
    if set(STEM_ORDER).issubset(keys):
        return STEM_ORDER
    if set(DEMUCS_STEM_ORDER).issubset(keys):
        return DEMUCS_STEM_ORDER
    return None


def _missing_for_any_order(stems: dict[str, str]) -> list[str]:
    keys = set(stems)
    missing_prepared = set(STEM_ORDER) - keys
    missing_demucs = set(DEMUCS_STEM_ORDER) - keys
    missing = missing_prepared if len(missing_prepared) <= len(missing_demucs) else missing_demucs
    return sorted(missing)


async def _separate_stems(
    ctx: Any, inputs: list[Any], workspace: str
) -> dict[int, dict[str, str]] | None:
    try:
        from app.audio.deep.demucs_runner import run_demucs
    except ImportError as exc:  # pragma: no cover - optional [stems] extra
        await safe_info(ctx, f"stem separation unavailable ({exc}); classic render")
        return None

    result: dict[int, dict[str, str]] = {}
    await safe_info(ctx, f"stem render: separating {len(inputs)} tracks (demucs)...")
    for ti in inputs:
        input_file = Path(ti.file_path)
        if not input_file.exists():
            await safe_info(ctx, f"missing audio for track {ti.track_id}; classic fallback")
            return None
        try:
            stems = run_demucs(
                input_file,
                Path("/tmp/dj_stems"),
                cache_root=Path(workspace) / "stems",
                flac=True,
            )
        except Exception as exc:
            await safe_info(ctx, f"demucs failed ({exc}); classic fallback")
            return None
        mapped = _expand_stem_paths(stems)
        missing = set(DEMUCS_STEM_ORDER) - set(mapped)
        if missing:
            await safe_info(
                ctx,
                "demucs output missing stems "
                f"{sorted(missing)} for track {ti.track_id}; classic fallback",
            )
            return None
        result[ti.track_id] = mapped

    await safe_info(ctx, f"stem render: {len(result)} tracks separated")
    return result


class StemResolver:
    async def resolve(
        self,
        ctx: Any,
        uow: Any,
        inputs: list[Any],
        workspace: str | None = None,
    ) -> dict[int, dict[str, str]] | None:
        if not inputs:
            return None

        session = getattr(uow, "session", None)
        if session is None:
            return await _separate_stems(ctx, inputs, workspace) if workspace else None

        track_ids = [ti.track_id for ti in inputs]
        stmt = select(DjLibraryItem.track_id, DjLibraryItem.file_path).where(
            DjLibraryItem.track_id.in_(track_ids)
        )
        rows = (await session.execute(stmt)).all()
        by_track: dict[int, dict[str, str]] = {tid: {} for tid in track_ids}
        for row in rows:
            for stem in _stem_type_from_path(row.file_path):
                by_track[row.track_id][stem] = row.file_path

        orders: dict[int, tuple[str, ...]] = {}
        missing = {}
        for tid, stems in by_track.items():
            order = _complete_stem_order(stems)
            if order is None:
                missing[tid] = _missing_for_any_order(stems)
            else:
                orders[tid] = order
        if missing:
            await safe_info(
                ctx,
                "prepared stem render unavailable; missing stems for "
                f"{len(missing)}/{len(track_ids)} tracks",
            )
            return await _separate_stems(ctx, inputs, workspace) if workspace else None
        if len(set(orders.values())) > 1:
            await safe_info(ctx, "prepared stem render unavailable; mixed stem layouts")
            return await _separate_stems(ctx, inputs, workspace) if workspace else None

        missing_files = {
            tid: sorted({path for path in stems.values() if not Path(path).exists()})
            for tid, stems in by_track.items()
        }
        missing_files = {tid: paths for tid, paths in missing_files.items() if paths}
        if missing_files:
            await safe_info(
                ctx,
                "prepared stem render unavailable; missing files for "
                f"{len(missing_files)}/{len(track_ids)} tracks",
            )
            return await _separate_stems(ctx, inputs, workspace) if workspace else None

        await safe_info(
            ctx,
            f"prepared stem render: loaded {len(by_track)} tracks",
        )
        return by_track
