"""Assemble + run the ffmpeg render command. Ported from render()."""

from __future__ import annotations

import shutil
import subprocess

from app.domain.render.graph import build_filtergraph
from app.domain.render.models import RenderPlan


def build_preprocess_cmd(track_path: str, out_path: str, eq_filter: str) -> list[str]:
    """Pre-process one track: HPF + EQ + soft compression → temp WAV."""
    return [
        "ffmpeg",
        "-y",
        "-i", track_path,
        "-af",
        f"highpass=f=30:t=4,"
        f"{eq_filter},"
        f"acompressor=threshold=-18dB:ratio=3:attack=10:release=80:"
        f"knee=6:detection=rms:link=average:makeup=1",
        "-c:a", "pcm_s16le",
        out_path,
    ]


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
        "-q:a", "0",
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
