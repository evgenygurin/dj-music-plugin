"""Assemble + run the ffmpeg render command. Ported from render()."""

from __future__ import annotations

import shutil
import subprocess

from app.domain.render.graph import build_filtergraph
from app.domain.render.models import RenderPlan


def build_ffmpeg_cmd(plan: RenderPlan, out_path: str) -> list[str]:
    """One ``-i`` per segment (in index order) + the filtergraph + mp3 out."""
    inputs: list[str] = []
    for seg in plan.segments:
        inputs += ["-i", seg.file_path]
    graph = ";".join(build_filtergraph(plan))
    return [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        graph,
        "-map",
        "[mix]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "320k",
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
