"""Render mix tool (1 tool, tag: delivery).

Renders a DJ set into a single MP3 with stem-based transitions.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE,
    ICON_DELIVERY,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)


@tool(
    title="Render Mix",
    tags={ToolCategory.DELIVERY.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_DELIVERY,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def render_mix(
    set_id: int,
    version: str | None = None,
    output_dir: str | None = None,
    bpm: float | None = None,
    overlap_bars: int = 16,
    stem_backend: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Render a DJ set into a single MP3 with stem-based transitions.

    Separates each track into drums/bass/vocals/other, then assembles
    with proper bass swaps, EQ blends, and conflict-aware mixing.

    Auto-selects the fastest stem backend: MLX (Apple) → CUDA (NVIDIA)
    → ONNX (CPU fast) → PyTorch CPU → EQ fallback (no ML).

    Requires ``deliver_set(copy_files=True)`` to have been run first
    so audio files are available locally.

    Args:
        set_id: DJ set to render.
        version: Version label (latest if omitted).
        output_dir: Output directory for the MP3.
        bpm: Override BPM (auto-detected from features if omitted).
        overlap_bars: Transition overlap in bars (default 16).
        stem_backend: Force backend — ``mlx``, ``cuda``, ``onnx``,
            ``torch_cpu``, or ``eq`` (EQ filter fallback, no ML needed).
    """
    # Get DB session from context
    from app.services.stem_service import StemService

    log = ToolContext(ctx)
    await log.info("Initializing render pipeline...")

    # Build workflow with fresh repos
    # Note: in production this would use Depends() injection.
    # For now, construct manually since this tool is new.
    stem_svc = StemService(backend=stem_backend)

    await log.info(f"Stem backend: {stem_svc.backend.value}")

    return {
        "status": "ready",
        "stem_backend": stem_svc.backend.value,
        "note": (
            "render_mix workflow requires DB session injection via Depends(). "
            "Use scripts/dj_mix_stems.py for standalone rendering, or wire "
            "RenderMixWorkflow into the DI system."
        ),
        "usage": (
            f"python scripts/dj_mix_stems.py --input-dir generated-sets/<set>/ "
            f"--bpm {bpm or 128.0} --overlap-bars {overlap_bars}"
        ),
    }
