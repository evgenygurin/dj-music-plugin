from __future__ import annotations

import asyncio
import gc
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.domain.render.models import STEM_ORDER
from app.handlers._context_log import safe_info
from app.models.audio_file import DjLibraryItem

# Serialize stem separation — shared with app/tools/stems.py (same unified memory).
# On M2 8GB two parallel MPS graphs OOM — Semaphore(1) + to_thread keeps MCP
# event loop responsive. Imported from app.audio.deep for single source of truth.
try:
    from app.audio.deep import STEMS_SEMAPHORE as _SEM
except ImportError:  # pragma: no cover - circular import fallback
    _SEM = asyncio.Semaphore(1)

_STEM_EXTENSIONS = (".m4a", ".mp3", ".wav", ".flac")

_STEM_ALIASES: dict[str, tuple[str, ...]] = {
    **{stem: (stem,) for stem in STEM_ORDER},
    "other": ("other",),
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

    Demucs-native ``other`` is mapped to ``harmonic`` (pads / leads).
    """
    result: dict[str, str] = {}
    for key, path in stems.items():
        internal_stems = _stem_type_from_path(str(key)) or _stem_type_from_path(str(path))
        for stem in internal_stems:
            if stem == "other":
                result["harmonic"] = str(path)
            else:
                result[stem] = str(path)
    return result


def _complete_stem_order(stems: dict[str, str]) -> tuple[str, ...] | None:
    """Return ``STEM_ORDER`` if all required stems are present."""
    return STEM_ORDER if set(STEM_ORDER).issubset(stems) else None


def _missing_for_any_order(stems: dict[str, str]) -> list[str]:
    return sorted(set(STEM_ORDER) - set(stems))


async def _separate_stems(
    ctx: Any, inputs: list[Any], workspace: str
) -> dict[int, dict[str, str]] | None:
    try:
        from app.audio.deep import get_runner
        from app.config.stems import StemsConfig
    except ImportError as exc:  # pragma: no cover - optional [stems] extra
        await safe_info(ctx, f"stem separation unavailable ({exc}); classic render")
        return None

    cfg = StemsConfig()
    try:
        runner = get_runner(cfg)
    except Exception as exc:  # pragma: no cover - runner resolution failed
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
            async with _SEM:
                stems = await asyncio.to_thread(
                    runner,
                    input_file,
                    Path(workspace) / "stems",
                    model=cfg.model,
                    flac=True,
                )
                # cleanup after each track (M2 8GB: free unified memory)
                try:
                    gc.collect()
                    try:
                        import torch

                        if torch.backends.mps.is_available():
                            torch.mps.empty_cache()
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception as exc:
            await safe_info(ctx, f"demucs failed ({exc}); classic fallback")
            return None
        mapped = _expand_stem_paths(stems)
        missing = set(STEM_ORDER) - set(mapped)
        if missing:
            await safe_info(
                ctx,
                "demucs output missing stems "
                f"{sorted(missing)} for track {ti.track_id}; classic fallback",
            )
            return None
        result[ti.track_id] = mapped
        # extra gc between tracks (outside semaphore, still frees memory)
        try:
            gc.collect()
            try:
                import torch

                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
            except Exception:
                pass
        except Exception:
            pass

    await safe_info(ctx, f"stem render: {len(result)} tracks ready")
    return result


def _find_cached_stems(input_file: Path, output_dir: str | None = None) -> dict[str, str] | None:
    """Reuse ready flac stems from any render workspace (per-file hash cache).

    ``run_demucs`` keys its cache on ``sha256(resolved_path)[:12]`` under
    ``{cache_root}/{stem}_{hash}/htdemucs/{stem}/``. Since each render
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
        stem_dir = stems_root / f"{stem}_{cache_key}" / "htdemucs" / stem
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
                if stem == "other":
                    by_track[row.track_id]["harmonic"] = row.file_path
                else:
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
