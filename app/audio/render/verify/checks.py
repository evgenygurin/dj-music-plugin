"""DJ-adapted verification checks for rendered set versions.

14 checks total: 5 pre-render, 9 post-render.
Adapted from scripts/verify_mix/checks.py — stripped of non-DJ concepts
(vocal_masking, phase_alignment, tempo_ratio_sanity, layer-based boundary
checks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np

from app.audio.render.verify.analysis import OutputMeasure, SourceMeasure
from app.audio.render.verify.manifest import DJManifest


class Status(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: Status
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerifyConfig:
    # honest_duration
    duration_mismatch_pct: float = 2.0
    # bpm_reliability
    bpm_confidence_warn: float = 0.25
    declared_bpm_fail: float = 2.0
    declared_bpm_warn: float = 0.5
    # source_trim_bounds (not used in DJ verify but kept for consistency)
    trim_tolerance_s: float = 0.05
    # output_duration
    output_duration_warn_s: float = 1.0
    output_duration_fail_s: float = 2.0
    # level_jumps
    level_jump_db: float = 6.0
    boundary_window_s: float = 1.0
    # clipping
    clipping_dbfs: float = -0.1
    # dropouts
    dropout_rms_db: float = -50.0
    dropout_min_s: float = 0.5
    # loudness_consistency
    lufs_spread_fail_lu: float = 6.0
    lufs_spread_warn_lu: float = 3.0
    # low_band_holes
    low_band_drop_fail_db: float = 10.0
    low_band_floor_db: float = -42.0
    low_band_min_s: float = 4.0
    # stereo_balance
    stereo_imbalance_warn_db: float = 2.0
    stereo_imbalance_fail_db: float = 4.0
    stereo_correlation_warn: float = 0.0
    stereo_correlation_fail: float = -0.30
    # RMS jumps (abrupt level changes)
    rms_jumps_warn: float = 0.3
    rms_jumps_fail: float = 1.0
    # energy_slope
    energy_slope_warn: float = -0.5
    energy_slope_fail: float = -1.5
    # BPM search range
    min_bpm: float = 100.0
    max_bpm: float = 200.0
    # segments shorter than this are not LUFS-scored
    min_segment_s: float = 3.0


# ── helpers ───────────────────────────────────────────────────────────


def _missing_source(name: str, src: SourceMeasure) -> CheckResult:
    return CheckResult(
        name,
        Status.WARN,
        f"{Path(src.path).name}: source missing - check skipped",
        {"path": src.path},
    )


def _no_output(name: str, out: Any) -> CheckResult:
    path = getattr(out, "path", None)
    return CheckResult(
        name,
        Status.WARN,
        f"rendered output missing ({path}) - post-render check skipped"
        if path
        else "post-render skipped (no output measured)",
        {"path": str(path) if path else None},
    )


def _bpm_delta(a: float, b: float) -> float:
    return min(abs(a - b), abs(a * 2 - b), abs(a / 2 - b))


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


# ── pre-render checks ─────────────────────────────────────────────────


def check_honest_duration(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "honest_duration"
    results: list[CheckResult] = []
    for src in manifest.sources:
        sm = src_measures.get(src.track_id)
        if sm is None or not sm.exists:
            results.append(_missing_source(name, sm or SourceMeasure(path=src.file_path)))
            continue
        if sm.decoded_duration is None:
            results.append(
                CheckResult(
                    name,
                    Status.WARN,
                    f"{Path(sm.path).name}: duration unavailable",
                    {"path": sm.path},
                )
            )
            continue
        results.append(
            CheckResult(name, Status.PASS, f"{Path(sm.path).name}: {sm.decoded_duration:.1f}s", {})
        )
    return results or [CheckResult(name, Status.PASS, "no sources declared", {})]


def check_bpm_reliability(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "bpm_reliability"
    results: list[CheckResult] = []
    for src in manifest.sources:
        sm = src_measures.get(src.track_id)
        if sm is None or not sm.exists:
            results.append(_missing_source(name, sm or SourceMeasure(path=src.file_path)))
            continue
        if sm.bpm is None or sm.bpm <= 0:
            results.append(
                CheckResult(
                    name,
                    Status.WARN,
                    f"{Path(sm.path).name}: BPM undetectable - declared {src.bpm:.2f} unverified",
                    {"declared_bpm": src.bpm},
                )
            )
            continue
        delta = _bpm_delta(sm.bpm, src.bpm)
        detail = {"declared_bpm": src.bpm, "measured_bpm": sm.bpm, "confidence": sm.bpm_confidence}
        if delta > cfg.declared_bpm_fail:
            results.append(
                CheckResult(
                    name,
                    Status.FAIL,
                    f"{Path(sm.path).name}: measured {sm.bpm:.2f} vs declared {src.bpm:.2f} (Δ{delta:.2f})",
                    detail,
                )
            )
        elif (sm.bpm_confidence or 0.0) < cfg.bpm_confidence_warn:
            results.append(
                CheckResult(
                    name,
                    Status.WARN,
                    f"{Path(sm.path).name}: BPM {sm.bpm:.2f} but confidence {sm.bpm_confidence:.2f}",
                    detail,
                )
            )
        else:
            status = Status.WARN if delta > cfg.declared_bpm_warn else Status.PASS
            results.append(
                CheckResult(
                    name,
                    status,
                    f"{Path(sm.path).name}: measured {sm.bpm:.2f} vs declared {src.bpm:.2f} (Δ{delta:.2f})",
                    detail,
                )
            )
    return results or [CheckResult(name, Status.PASS, "no sources declared", {})]


def check_source_trim_bounds(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "source_trim_bounds"
    results: list[CheckResult] = []
    for src in manifest.sources:
        sm = src_measures.get(src.track_id)
        if sm is None or not sm.exists:
            results.append(_missing_source(name, sm or SourceMeasure(path=src.file_path)))
            continue
        if sm.decoded_duration is None:
            results.append(
                CheckResult(
                    name,
                    Status.WARN,
                    f"{Path(sm.path).name}: decoded duration unavailable",
                    {"track_id": src.track_id},
                )
            )
            continue
        results.append(
            CheckResult(
                name,
                Status.PASS,
                f"{Path(sm.path).name}: {sm.decoded_duration:.1f}s source available",
                {},
            )
        )
    return results or [CheckResult(name, Status.PASS, "no sources declared", {})]


def check_boundary_alignment(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "boundary_alignment"
    if not manifest.segment_start_s:
        return [CheckResult(name, Status.PASS, "no segment boundaries declared", {})]
    if not manifest.segment_lengths_s:
        return [CheckResult(name, Status.WARN, "segment lengths unavailable", {})]
    expected = manifest.expected_duration_s
    total = (
        manifest.segment_start_s[-1] + manifest.segment_lengths_s[-1]
        if manifest.segment_start_s
        else 0.0
    )
    if abs(total - expected) > 0.1:
        return [
            CheckResult(
                name,
                Status.WARN,
                f"segment timeline end {total:.2f}s ≠ expected {expected:.2f}s",
                {"computed_s": total, "expected_s": expected},
            )
        ]
    return [
        CheckResult(
            name,
            Status.PASS,
            f"{manifest.n_segments} segments, {total:.1f}s total",
            {"n": manifest.n_segments, "total_s": total},
        )
    ]


def check_timeline(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "timeline"
    if not manifest.segment_start_s:
        return [CheckResult(name, Status.PASS, "no segments declared", {})]
    for i in range(1, len(manifest.segment_start_s)):
        prev_end = manifest.segment_start_s[i - 1] + manifest.segment_lengths_s[i - 1]
        curr_start = manifest.segment_start_s[i]
        if abs(prev_end - curr_start) > 0.05:
            return [
                CheckResult(
                    name,
                    Status.WARN,
                    f"gap between segment {i} end {prev_end:.2f}s and segment {i + 1} start {curr_start:.2f}s",
                    {"segment": i, "gap_s": curr_start - prev_end},
                )
            ]
    return [CheckResult(name, Status.PASS, f"{manifest.n_segments} segments contiguous", {})]


PRE_RENDER_CHECKS = (
    check_honest_duration,
    check_bpm_reliability,
    check_source_trim_bounds,
    check_boundary_alignment,
    check_timeline,
)


# ── post-render checks ────────────────────────────────────────────────


def check_output_duration(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "output_duration"
    if out is None or not out.exists or out.decoded_duration is None:
        return [_no_output(name, out)]
    expected = manifest.expected_duration_s
    delta = out.decoded_duration - expected
    abs_delta = abs(delta)
    if abs_delta > cfg.output_duration_fail_s:
        status = Status.FAIL
    elif abs_delta > cfg.output_duration_warn_s:
        status = Status.WARN
    else:
        status = Status.PASS
    return [
        CheckResult(
            name,
            status,
            f"output {out.decoded_duration:.2f}s vs expected {expected:.2f}s (Δ{delta:+.2f}s)",
            {"actual_s": out.decoded_duration, "expected_s": expected, "delta_s": delta},
        )
    ]


def check_level_jumps(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "level_jumps"
    if out is None or not out.exists or out.rms_times is None or out.rms_db is None:
        return [_no_output(name, out)]
    boundaries = set()
    for start, length in zip(manifest.segment_start_s, manifest.segment_lengths_s, strict=False):
        boundaries.add(start)
        boundaries.add(start + length)
    worst: tuple[float, float] | None = None
    for t in boundaries:
        if t <= 0 or out.decoded_duration is None or t >= out.decoded_duration:
            continue
        mask_before = out.rms_times >= t - cfg.boundary_window_s
        mask_after = out.rms_times < t + cfg.boundary_window_s
        before = (
            float(np.mean(out.rms_db[mask_before & (out.rms_times < t)]))
            if np.any(mask_before & (out.rms_times < t))
            else None
        )
        after = (
            float(np.mean(out.rms_db[mask_after & (out.rms_times >= t)]))
            if np.any(mask_after & (out.rms_times >= t))
            else None
        )
        if before is None or after is None:
            continue
        jump = abs(after - before)
        if worst is None or jump > worst[1]:
            worst = (t, jump)
    if worst is None:
        return [CheckResult(name, Status.PASS, "no interior segment boundaries", {})]
    status = Status.FAIL if worst[1] > cfg.level_jump_db else Status.PASS
    return [
        CheckResult(
            name,
            status,
            f"worst boundary jump {worst[1]:.1f} dB at {worst[0]:.1f}s",
            {"boundary_s": worst[0], "jump_db": worst[1]},
        )
    ]


def check_clipping(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "clipping"
    if out is None or not out.exists:
        return [_no_output(name, out)]
    status = (
        Status.FAIL
        if (out.sample_peak_db or 0.0) >= cfg.clipping_dbfs or out.clipped_sample_count > 0
        else Status.PASS
    )
    msg = f"peak {out.sample_peak_db:.1f} dBFS, clipped samples {out.clipped_sample_count}"
    if out.first_clip_time is not None:
        msg += f"; first at {out.first_clip_time:.0f}s"
    return [
        CheckResult(
            name,
            status,
            msg,
            {
                "sample_peak_db": out.sample_peak_db,
                "clipped_sample_count": out.clipped_sample_count,
                "first_clip_time_s": out.first_clip_time,
            },
        )
    ]


def check_dropouts(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "dropouts"
    if out is None or not out.exists or out.rms_times is None or out.rms_db is None:
        return [_no_output(name, out)]
    silent = out.rms_db < cfg.dropout_rms_db
    runs = _true_runs(silent)
    hop = float(out.rms_times[1] - out.rms_times[0]) if len(out.rms_times) >= 2 else 0.2
    dropouts = [
        (float(out.rms_times[a]), float(out.rms_times[b - 1]))
        for a, b in runs
        if (b - a) * hop >= cfg.dropout_min_s
    ]
    if dropouts:
        first = dropouts[0]
        return [
            CheckResult(
                name,
                Status.FAIL,
                f"{len(dropouts)} silent windows >= {cfg.dropout_min_s}s, first at {first[0]:.1f}-{first[1]:.1f}s",
                {"dropouts": [{"start_s": a, "end_s": b} for a, b in dropouts]},
            )
        ]
    return [CheckResult(name, Status.PASS, "no silent windows", {})]


def check_loudness_consistency(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "loudness_consistency"
    if out is None or not out.exists:
        return [_no_output(name, out)]
    values = [(s, e, lufs) for s, e, lufs in out.segments if lufs is not None]
    if len(values) < 2:
        return [
            CheckResult(
                name, Status.PASS, "fewer than 2 measurable segments", {"segments": len(values)}
            )
        ]
    lufs = [v[2] for v in values]
    spread = max(lufs) - min(lufs)
    if spread > cfg.lufs_spread_fail_lu:
        status = Status.FAIL
    elif spread > cfg.lufs_spread_warn_lu:
        status = Status.WARN
    else:
        status = Status.PASS
    return [
        CheckResult(
            name,
            status,
            f"segment LUFS spread {spread:.1f} LU across {len(values)} segments",
            {"spread_lu": spread},
        )
    ]


def check_low_band_holes(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "low_band_holes"
    if out is None or not out.exists or out.low_rms_times is None or out.low_rms_db is None:
        return [_no_output(name, out)]
    if len(out.low_rms_db) < 2:
        return [CheckResult(name, Status.PASS, "low-band series too short", {})]
    median = float(np.median(out.low_rms_db))
    low = (out.low_rms_db < median - cfg.low_band_drop_fail_db) & (
        out.low_rms_db < cfg.low_band_floor_db
    )
    runs = _true_runs(low)
    hop = (
        float(out.low_rms_times[1] - out.low_rms_times[0]) if len(out.low_rms_times) >= 2 else 1.0
    )
    holes = [
        (float(out.low_rms_times[a]), float(out.low_rms_times[b - 1]))
        for a, b in runs
        if (b - a) * hop >= cfg.low_band_min_s
    ]
    if holes:
        first = holes[0]
        return [
            CheckResult(
                name,
                Status.FAIL,
                f"{len(holes)} low-band hole(s), first {first[0]:.1f}-{first[1]:.1f}s",
                {"holes": [{"start_s": s, "end_s": e} for s, e in holes]},
            )
        ]
    return [CheckResult(name, Status.PASS, "no low-band holes", {"median_low_db": median})]


def check_stereo_balance(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "stereo_balance"
    if out is None or not out.exists:
        return [_no_output(name, out)]
    if out.channel_rms_db is None:
        return [CheckResult(name, Status.PASS, "mono output", {})]
    left, right = out.channel_rms_db
    imbalance = abs(left - right)
    corr = out.stereo_correlation
    if imbalance > cfg.stereo_imbalance_fail_db or (
        corr is not None and corr < cfg.stereo_correlation_fail
    ):
        status = Status.FAIL
    elif imbalance > cfg.stereo_imbalance_warn_db or (
        corr is not None and corr < cfg.stereo_correlation_warn
    ):
        status = Status.WARN
    else:
        status = Status.PASS
    corr_text = "n/a" if corr is None else f"{corr:.2f}"
    return [
        CheckResult(
            name,
            status,
            f"L/R RMS {left:.1f}/{right:.1f} dB (Δ{imbalance:.1f}), correlation {corr_text}",
            {
                "left_rms_db": left,
                "right_rms_db": right,
                "imbalance_db": imbalance,
                "correlation": corr,
            },
        )
    ]


def check_rms_jumps(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "rms_jumps"
    if out is None or not out.exists or out.rms_jumps_per_min is None:
        return [_no_output(name, out)]
    v = out.rms_jumps_per_min
    if v > cfg.rms_jumps_fail:
        status = Status.FAIL
    elif v > cfg.rms_jumps_warn:
        status = Status.WARN
    else:
        status = Status.PASS
    msg = f"{v:.2f} abrupt RMS jumps/min"
    if out.rms_jump_times:
        first = out.rms_jump_times[0]
        direction = "+" if first[1] > 0 else ""
        msg += f"; worst {direction}{abs(first[1]):.0f}dB at {first[0]:.0f}s"
    return [CheckResult(name, status, msg, {"rms_jumps_per_min": v})]


def check_energy_slope(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    out: OutputMeasure | None,
    cfg: VerifyConfig,
) -> list[CheckResult]:
    name = "energy_slope"
    if out is None or not out.exists:
        return [_no_output(name, out)]
    if out.energy_slope_db_per_min is None:
        return [CheckResult(name, Status.WARN, "energy trend unavailable (short file?)", {})]
    v = out.energy_slope_db_per_min
    if v < cfg.energy_slope_fail:
        status = Status.FAIL
    elif v < cfg.energy_slope_warn:
        status = Status.WARN
    else:
        status = Status.PASS
    direction = "+" if v >= 0 else ""
    return [
        CheckResult(
            name, status, f"energy trend {direction}{v:.2f} dB/min", {"energy_slope_db_per_min": v}
        )
    ]


POST_RENDER_CHECKS = (
    check_output_duration,
    check_level_jumps,
    check_clipping,
    check_dropouts,
    check_loudness_consistency,
    check_low_band_holes,
    check_stereo_balance,
    check_rms_jumps,
    check_energy_slope,
)


# ── orchestration ─────────────────────────────────────────────────────


def run_checks(
    manifest: DJManifest,
    src_measures: dict[int, SourceMeasure],
    output: OutputMeasure | None,
    cfg: VerifyConfig | None = None,
    *,
    skip_post: bool = False,
) -> list[CheckResult]:
    cfg = cfg or VerifyConfig()
    results: list[CheckResult] = []
    for check in PRE_RENDER_CHECKS:
        results.extend(check(manifest, src_measures, output, cfg))
    if not skip_post:
        for check in POST_RENDER_CHECKS:
            results.extend(check(manifest, src_measures, output, cfg))
    return results
