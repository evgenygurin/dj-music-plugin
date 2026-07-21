"""Assemble + run the ffmpeg render command (domain-side; audio-less)."""

from __future__ import annotations

import shutil
import subprocess

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
