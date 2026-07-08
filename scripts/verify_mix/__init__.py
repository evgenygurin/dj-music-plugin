"""Mix-verify — check an assembled multi-source track against its build plan.

Reads the build manifest (the single source of truth the ffmpeg graph is
generated from) plus the rendered output and runs a battery of checks for
the failure modes that hand-built mixes keep hitting: ffprobe duration
lies, quantized BPM detection, wrong tempo ratios, phase/downbeat drift,
vocal masking, level jumps, clipping, dropouts, loudness inconsistency.

See docs/superpowers/specs/2026-07-07-mix-verify-design.md.
"""

from __future__ import annotations

from .checks import CheckResult, Status, run_all_checks
from .manifest import Layer, Manifest, load_manifest
from .report import Report, build_report

__all__ = [
    "CheckResult",
    "Layer",
    "Manifest",
    "Report",
    "Status",
    "build_report",
    "load_manifest",
    "run_all_checks",
]
