from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.domain.render.models import (
    DEMUCS_STEM_ORDER,
    LEGACY_PREPARED_STEM_ORDER,
    STEM_ORDER,
)
from app.handlers._context_log import safe_info
from app.models.audio_file import DjLibraryItem

_STEM_EXTENSIONS = (".m4a", ".mp3", ".wav", ".flac")

# Map prepared-stem filenames (legacy 5-stem layout) to canonical stem names.
# This is the ONLY place legacy aliases are translated to the new electronic
# music taxonomy (``instrumental`` → ``harmonic`` alias, etc.).
_LEGACY_STEM_ALIASES: dict[str, str] = {
    "instrumental": "harmonic",
    "acappella": "vocals",
    "other": "harmonic",
}

_STEM_ALIASES: dict[str, tuple[str, ...]] = {
    **{stem: (stem,) for stem in STEM_ORDER},
    **{stem: (stem,) for stem in DEMUCS_STEM_ORDER},
    **{stem: (stem,) for stem in LEGACY_PREPARED_STEM_ORDER},
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
    """Expand raw stem dict to canonical electronic-music taxonomy keys.

    Translates legacy prepared-stem aliases (``instrumental``,
    ``acappella``) into the new canonical names (``harmonic``,
    ``vocals``). Demucs-native ``other`` is also mapped to ``harmonic``.
    """
    result: dict[str, str] = {}
    for key, path in stems.items():
        internal_stems = _stem_type_from_path(str(key)) or _stem_type_from_path(str(path))
        for stem in internal_stems:
            canonical = _LEGACY_STEM_ALIASES.get(stem, stem)
            result[canonical] = str(path)
    return result


def _complete_stem_order(stems: dict[str, str]) -> tuple[str, ...] | None:
    """Return the canonical STEM_ORDER if all required stems are present."""
    keys = set(stems)
    if set(STEM_ORDER).issubset(keys):
        return STEM_ORDER
    if set(DEMUCS_STEM_ORDER).issubset(keys):
        return DEMUCS_STEM_ORDER
    if set(LEGACY_PREPARED_STEM_ORDER).issubset(keys):
        return LEGACY_PREPARED_STEM_ORDER
    return None


def _missing_for_any_order(stems: dict[str, str]) -> list[str]:
    """Return the missing stems for the closest matching order."""
    keys = set(stems)
    missing_prepared = set(LEGACY_PREPARED_STEM_ORDER) - keys
    missing_demucs = set(DEMUCS_STEM_ORDER) - keys
    missing = missing_prepared if len(missing_prepared) <= len(missing_demucs) else missing_demucs
    return sorted(missing)


async def _separate_stems(
    ctx: Any, inputs: list[Any], workspace: str
) -> dict[int, dict[str, str]] | None:
    try:
        from app.audio.deep.demucs_runner import DEFAULT_DEMUCS_MODEL, run_demucs
    except ImportError as exc:  # pragma: no cover - optional [stems] extra
        await safe_info(ctx, f"stem separation unavailable ({exc}); classic render")
        return None

    result: dict[int, dict[str, str]] = {}
    for ti in inputs:
        input_file = Path(ti.file_path)
        if not input_file.exists():
            await safe_info(ctx, f"missing audio for track {ti.track_id}; classic fallback")
            return None
        cached = _find_cached_stems(input_file)
        if cached is not None:
            result[ti.track_id] = cached
            continue
        await safe_info(
            ctx, f"stem render: separating track {ti.track_id} ({Path(ti.file_path).name})..."
        )
        try:
            stems = await asyncio.to_thread(
                run_demucs,
                input_file,
                cache_root=Path(workspace) / "stems",
                flac=True,
                model=DEFAULT_DEMUCS_MODEL,
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

    await safe_info(ctx, f"stem render: {len(result)} tracks ready")
    return result


def _find_cached_stems(input_file: Path, output_dir: str | None = None) -> dict[str, str] | None:
    """Reuse ready flac stems from any render workspace (per-file hash cache).

    ``run_demucs`` keys its cache on ``sha256(resolved_path)[:12]`` under
    ``{cache_root}/{stem}_{hash}/<model>/{stem}/``. Since each render
    workspace seeds that cache, a track already separated for another version
    must not be separated again — scan every ``output_dir/render/*/stems``
    for the matching directory and return its stems directly.
    """
    import hashlib

    if output_dir is None:
        from app.config import get_settings

        output_dir = get_settings().delivery.output_dir

    cache_key = hashlib.sha256(str(input_file.resolve()).encode()).hexdigest()[:12]
    stem = input_file.stem
    want = {
        "vocals": "vocals.flac",
        "drums": "drums.flac",
        "bass": "bass.flac",
        "harmonic": "harmonic.flac",
        "percussion": "percussion.flac",
    }
    output_root = Path(output_dir)
    for stems_root in sorted(output_root.glob("render/*/stems")):
        # Phase 1: prefer htdemucs_6s cache; fall back to htdemucs for
        # previously-cached outputs that predate the 6s switch.
        for model in ("htdemucs_6s", "htdemucs"):
            stem_dir = stems_root / f"{stem}_{cache_key}" / model / stem
            if not stem_dir.is_dir():
                continue
            found = {name: str(stem_dir / fname) for name, fname in want.items()}
            if all(Path(p).exists() for p in found.values()):
                return found
    return None


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
                canonical = _LEGACY_STEM_ALIASES.get(stem, stem)
                by_track[row.track_id][canonical] = row.file_path

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
