"""Assemble + run the ffmpeg render command (domain-side; audio-less)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

from app.domain.render.filtergraph import select_strategy
from app.domain.render.models import RenderPlan

# 320 kbps CBR MP3, highest LAME quality — the render deliverable format.
_MP3_ENCODE_ARGS: list[str] = ["-c:a", "libmp3lame", "-b:a", "320k", "-q:a", "0"]


def build_ffmpeg_cmd(plan: RenderPlan, out_path: str) -> list[str]:
    """Assemble the ffmpeg render command for the plan's render strategy.

    The strategy expands the ``-i`` inputs (one file per classic track, four
    stems per stem track) and builds the matching filtergraph — the command
    shell is identical for both modes.
    """
    strategy = select_strategy(plan)
    inputs: list[str] = []
    for file_path in strategy.input_files(plan):
        inputs += ["-i", file_path]
    graph = ";".join(strategy.filtergraph(plan))
    return [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        graph,
        "-map",
        "[mix]",
        *_MP3_ENCODE_ARGS,
        out_path,
    ]


def run_render(plan: RenderPlan, out_path: str) -> None:
    """Run ffmpeg. Raises RuntimeError on missing binary or non-zero exit."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found — install ffmpeg built with librubberband (brew install ffmpeg)."
        )
    cmd = build_ffmpeg_cmd(plan, out_path)
    r = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        tail = (r.stderr or "")[-2000:]
        raise RuntimeError(f"ffmpeg render failed: {tail}")


def run_render_with_progress(
    plan: RenderPlan,
    out_path: str,
    *,
    on_progress: Callable[[int, int, str], None],
) -> None:
    """Run ffmpeg while reporting encoded duration to the caller.

    This is used by interactive previews so the UI can show real progress
    instead of an opaque spinner. The normal production renderer keeps using
    ``run_render`` unchanged.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found — install ffmpeg built with librubberband.")
    cmd = build_ffmpeg_cmd(plan, out_path)
    cmd = [*cmd[:-1], "-progress", "pipe:1", "-nostats", cmd[-1]]
    expected = sum(
        (s.length_s for s in (plan.stem_segments or plan.segments)),
        0.0,
    )
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    ) as proc:
        assert proc.stdout is not None
        last_ms = 0
        for line in proc.stdout:
            if line.startswith("out_time_ms="):
                try:
                    last_ms = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                ratio = min(0.99, max(0.0, (last_ms / 1_000_000) / expected)) if expected else 0.0
                on_progress(
                    int(ratio * 100), int(expected * 1000), f"rendering {ratio * 100:.0f}%"
                )
        stderr = proc.stderr.read() if proc.stderr is not None else ""
        rc = proc.wait()
    if rc != 0:
        tail = (stderr or "")[-2000:]
        raise RuntimeError(f"ffmpeg render failed: {tail}")
    on_progress(100, int(expected * 1000), "preview ready")
