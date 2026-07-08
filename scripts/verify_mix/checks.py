"""Mix-verify checks - pure functions over (manifest, measurements, config).

Each check returns one or more :class:`CheckResult` with the actual
measured number and its threshold in the message, so a failing report is
directly actionable. Status semantics:

- PASS - measured value inside the threshold;
- WARN - suspicious but not provably broken (or the source needed for a
  hard verdict is missing);
- FAIL - provably violates the build plan; delivery must be gated.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np

from .analysis import Measurements, OutputMeasure, SourceMeasure, _true_runs
from .manifest import Layer, Manifest


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
    """Every threshold in one place."""

    # honest_duration
    duration_mismatch_pct: float = 2.0
    # bpm_reliability
    bpm_confidence_warn: float = 0.25
    declared_bpm_fail: float = 2.0
    declared_bpm_warn: float = 0.5
    # tempo_ratio_sanity
    tempo_ratio_bpm_tolerance: float = 1.0
    # phase_alignment
    phase_beat_fraction: float = 0.15
    # source_trim_bounds
    trim_tolerance_s: float = 0.05
    # boundary_alignment
    boundary_beat_fraction: float = 0.20
    boundary_bar_fraction: float = 0.35
    # timeline
    vocal_overlap_tolerance_s: float = 0.25
    # output_duration
    output_duration_warn_s: float = 1.0
    output_duration_fail_s: float = 2.0
    # vocal_masking
    vocal_over_bed_fail_db: float = -3.0
    vocal_over_bed_warn_db: float = 0.0
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
    # standalone: crest factor (dynamic range)
    crest_factor_warn_min: float = 3.0
    crest_factor_warn_max: float = 16.0
    crest_factor_fail_min: float = 1.5
    crest_factor_fail_max: float = 22.0
    # standalone: low-band spectral energy %
    low_band_warn_min: float = 8.0
    low_band_warn_max: float = 82.0
    low_band_fail_min: float = 3.0
    low_band_fail_max: float = 92.0
    # standalone: mid-band mud (250-500 Hz) %
    mid_mud_warn: float = 20.0
    mid_mud_fail: float = 30.0
    # standalone: high-band air %
    high_band_warn: float = 0.15
    high_band_fail: float = 0.05
    # standalone: low-end stereo correlation
    low_end_corr_warn: float = 0.50
    low_end_corr_fail: float = 0.20
    # standalone: integrated LUFS target
    lufs_warn_high: float = -5.0
    lufs_warn_low: float = -14.0
    lufs_fail_high: float = -3.5
    lufs_fail_low: float = -18.0
    # standalone: energy range (max RMS - min RMS)
    energy_range_warn_db: float = 30.0
    energy_range_fail_db: float = 38.0
    energy_range_edge_guard_s: float = 2.0
    # standalone: energy dip count (per minute)
    energy_dips_warn_per_min: float = 0.5
    energy_dips_fail_per_min: float = 2.0
    # standalone: BPM stability
    bpm_stability_warn: float = 2.0
    bpm_stability_fail: float = 5.0
    # standalone: RMS jumps per minute (abrupt level changes)
    rms_jumps_warn: float = 0.3
    rms_jumps_fail: float = 1.0
    # kick_consistency
    kick_drop_db: float = 8.0
    kick_drop_warn_s: float = 16.0
    kick_drop_fail_s: float = 32.0
    # energy_slope (dB per minute of mix time — negative = dying set)
    energy_slope_warn: float = -0.5
    energy_slope_fail: float = -1.5
    # BPM search range for the detector
    min_bpm: float = 100.0
    max_bpm: float = 200.0
    # segments shorter than this are not LUFS-scored
    min_segment_s: float = 3.0


def _missing(name: str, measure: SourceMeasure) -> CheckResult:
    return CheckResult(
        name,
        Status.WARN,
        f"{measure.path.name}: source missing - check skipped",
        {"path": str(measure.path)},
    )


# ── pre-render checks ────────────────────────────────────────────────


def check_honest_duration(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """ffprobe bitrate-estimate vs honest sample-count duration."""
    name = "honest_duration"
    results: list[CheckResult] = []
    sources = [m.backbone, *(m.layers[i] for i in sorted(m.layers))]
    for src in sources:
        if not src.exists:
            results.append(_missing(name, src))
            continue
        if src.decoded_duration is None or src.ffprobe_dur is None:
            results.append(
                CheckResult(
                    name,
                    Status.WARN,
                    f"{src.path.name}: could not compare durations",
                    {"path": str(src.path)},
                )
            )
            continue
        ref = max(src.decoded_duration, 1e-6)
        diff_pct = abs(src.ffprobe_dur - src.decoded_duration) / ref * 100.0
        status = Status.FAIL if diff_pct > cfg.duration_mismatch_pct else Status.PASS
        results.append(
            CheckResult(
                name,
                status,
                f"{src.path.name}: decoded {src.decoded_duration:.1f}s vs "
                f"ffprobe {src.ffprobe_dur:.1f}s "
                f"(Δ{diff_pct:.1f}% vs {cfg.duration_mismatch_pct:.0f}%)",
                {
                    "path": str(src.path),
                    "decoded_s": src.decoded_duration,
                    "ffprobe_s": src.ffprobe_dur,
                    "diff_pct": diff_pct,
                },
            )
        )
    return results


def check_bpm_reliability(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Backbone BPM must be detectable with confidence and match the
    declared manifest BPM."""
    name = "bpm_reliability"
    src = m.backbone
    if not src.exists:
        return [_missing(name, src)]
    if src.bpm is None or src.bpm <= 0:
        return [
            CheckResult(
                name,
                Status.WARN,
                f"{src.path.name}: BPM undetectable - declared "
                f"{manifest.backbone.bpm:.2f} unverified",
                {"declared_bpm": manifest.backbone.bpm},
            )
        ]

    detail = {
        "declared_bpm": manifest.backbone.bpm,
        "measured_bpm": src.bpm,
        "confidence": src.bpm_confidence,
    }
    delta = _bpm_delta(src.bpm, manifest.backbone.bpm)
    if delta > cfg.declared_bpm_fail:
        return [
            CheckResult(
                name,
                Status.FAIL,
                f"{src.path.name}: measured {src.bpm:.2f} BPM vs declared "
                f"{manifest.backbone.bpm:.2f} (Δ{delta:.2f} > {cfg.declared_bpm_fail})",
                detail,
            )
        ]
    if (src.bpm_confidence or 0.0) < cfg.bpm_confidence_warn:
        return [
            CheckResult(
                name,
                Status.WARN,
                f"{src.path.name}: BPM {src.bpm:.2f} but confidence "
                f"{src.bpm_confidence:.2f} < {cfg.bpm_confidence_warn}",
                detail,
            )
        ]
    status = Status.WARN if delta > cfg.declared_bpm_warn else Status.PASS
    return [
        CheckResult(
            name,
            status,
            f"{src.path.name}: measured {src.bpm:.2f} BPM vs declared "
            f"{manifest.backbone.bpm:.2f} (Δ{delta:.2f}, conf {src.bpm_confidence:.2f})",
            detail,
        )
    ]


def check_tempo_ratio_sanity(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """``source_bpm x tempo_ratio`` must land within tolerance of the
    backbone BPM. Vocal layers (no reliable percussion) only WARN."""
    name = "tempo_ratio_sanity"
    results: list[CheckResult] = []
    target = manifest.backbone.bpm
    for i, layer in enumerate(manifest.layers):
        src = m.layers.get(i)
        if src is None or not src.exists:
            results.append(_missing(name, src or SourceMeasure(manifest.layer_path(layer))))
            continue
        if src.bpm is None or src.bpm <= 0 or (src.bpm_confidence or 0) < cfg.bpm_confidence_warn:
            results.append(
                CheckResult(
                    name,
                    Status.WARN,
                    f"{src.path.name}: layer BPM unreliable "
                    f"(conf {src.bpm_confidence or 0:.2f}) - "
                    f"tempo_ratio {layer.tempo_ratio:.5f} unverified",
                    {"layer": i, "confidence": src.bpm_confidence},
                )
            )
            continue
        effective = src.bpm * layer.tempo_ratio
        delta = _bpm_delta(effective, target)
        bad = delta > cfg.tempo_ratio_bpm_tolerance
        status = (
            Status.FAIL if bad and layer.role == "bed" else (Status.WARN if bad else Status.PASS)
        )
        results.append(
            CheckResult(
                name,
                status,
                f"{src.path.name}: {src.bpm:.2f} x {layer.tempo_ratio:.5f} = "
                f"{effective:.2f} BPM vs backbone {target:.2f} "
                f"(Δ{delta:.2f} vs ±{cfg.tempo_ratio_bpm_tolerance})",
                {
                    "layer": i,
                    "source_bpm": src.bpm,
                    "tempo_ratio": layer.tempo_ratio,
                    "effective_bpm": effective,
                    "backbone_bpm": target,
                    "delta_bpm": delta,
                },
            )
        )
    return results


def check_phase_alignment(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Placed layer downbeats must fall near the backbone beat grid.

    Approximate by design - there is no authoritative beatgrid/deck, so
    misalignment is reported as WARN for vocals and FAIL only for bed
    layers with a confident grid.
    """
    name = "phase_alignment"
    results: list[CheckResult] = []
    backbone = m.backbone
    if not backbone.exists or backbone.beat_times is None or len(backbone.beat_times) < 4:
        return [
            CheckResult(
                name,
                Status.WARN,
                "backbone beat grid unavailable - phase alignment skipped",
                {},
            )
        ]
    beat_period = 60.0 / manifest.backbone.bpm

    for i, layer in enumerate(manifest.layers):
        src = m.layers.get(i)
        if src is None or not src.exists or src.beat_times is None:
            results.append(_missing(name, src or SourceMeasure(manifest.layer_path(layer))))
            continue
        placed = _placed_beats(layer, src.beat_times)
        if len(placed) < 4:
            results.append(
                CheckResult(
                    name,
                    Status.WARN,
                    f"{src.path.name}: too few beats in trimmed region - skipped",
                    {"layer": i, "beats": len(placed)},
                )
            )
            continue
        # Distance of each placed beat to the nearest backbone beat,
        # as a fraction of the beat period.
        deltas = np.min(
            np.abs(placed[:, None] - np.asarray(backbone.beat_times)[None, :]),
            axis=1,
        )
        median_frac = float(np.median(deltas) / beat_period)
        bad = median_frac > cfg.phase_beat_fraction
        status = (
            Status.FAIL if bad and layer.role == "bed" else (Status.WARN if bad else Status.PASS)
        )
        results.append(
            CheckResult(
                name,
                status,
                f"{src.path.name}: median beat offset {median_frac:.2f} of a beat "
                f"vs {cfg.phase_beat_fraction} (approximate - no deck beatgrid)",
                {"layer": i, "median_beat_fraction": median_frac},
            )
        )
    return results


def check_source_trim_bounds(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Layer trims must be inside the decoded source length."""
    name = "source_trim_bounds"
    if not manifest.layers:
        return [CheckResult(name, Status.PASS, "no layers declared", {})]
    results: list[CheckResult] = []
    for i, layer in enumerate(manifest.layers):
        src = m.layers.get(i)
        if src is None or not src.exists:
            results.append(_missing(name, src or SourceMeasure(manifest.layer_path(layer))))
            continue
        if src.decoded_duration is None:
            results.append(
                CheckResult(
                    name,
                    Status.WARN,
                    f"{src.path.name}: decoded duration unavailable - trim unverified",
                    {"layer": i},
                )
            )
            continue
        over_by = layer.src_trim[1] - src.decoded_duration
        if layer.src_trim[0] < -cfg.trim_tolerance_s or over_by > cfg.trim_tolerance_s:
            results.append(
                CheckResult(
                    name,
                    Status.FAIL,
                    f"{src.path.name}: trim {layer.src_trim[0]:.2f}-{layer.src_trim[1]:.2f}s "
                    f"outside decoded source length {src.decoded_duration:.2f}s",
                    {
                        "layer": i,
                        "trim_start_s": layer.src_trim[0],
                        "trim_end_s": layer.src_trim[1],
                        "decoded_s": src.decoded_duration,
                    },
                )
            )
        else:
            results.append(
                CheckResult(
                    name,
                    Status.PASS,
                    f"{src.path.name}: trim fits decoded source length "
                    f"{src.decoded_duration:.2f}s",
                    {"layer": i},
                )
            )
    return results


def check_boundary_alignment(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Layer starts/ends should land on the backbone beat grid and near bars."""
    name = "boundary_alignment"
    backbone = m.backbone
    if not manifest.layers:
        return [CheckResult(name, Status.PASS, "no layer boundaries declared", {})]
    if not backbone.exists or backbone.beat_times is None or len(backbone.beat_times) < 8:
        return [
            CheckResult(
                name,
                Status.WARN,
                "backbone beat grid unavailable - boundary alignment skipped",
                {},
            )
        ]
    beat_period = 60.0 / manifest.backbone.bpm
    beats = np.asarray(backbone.beat_times, dtype=np.float64)
    bars = beats[::4]
    results: list[CheckResult] = []
    for i, layer in enumerate(manifest.layers):
        worst_beat = 0.0
        worst_bar = 0.0
        worst_boundary = 0.0
        for boundary in (layer.place_at, layer.out_end):
            beat_frac = _nearest_delta_fraction(boundary, beats, beat_period)
            bar_frac = _nearest_delta_fraction(boundary, bars, beat_period)
            if beat_frac > worst_beat:
                worst_beat = beat_frac
                worst_boundary = boundary
            worst_bar = max(worst_bar, bar_frac)

        off_beat = worst_beat > cfg.boundary_beat_fraction
        off_bar = worst_bar > cfg.boundary_bar_fraction
        if off_beat and layer.role == "bed":
            status = Status.FAIL
        elif off_beat or off_bar:
            status = Status.WARN
        else:
            status = Status.PASS
        results.append(
            CheckResult(
                name,
                status,
                f"layer {i} ({layer.source.name}): worst boundary offset "
                f"{worst_beat:.2f} beat, bar offset {worst_bar:.2f} beat "
                f"(beat max {cfg.boundary_beat_fraction}, bar warn {cfg.boundary_bar_fraction})",
                {
                    "layer": i,
                    "role": layer.role,
                    "worst_boundary_s": worst_boundary,
                    "worst_beat_fraction": worst_beat,
                    "worst_bar_fraction": worst_bar,
                },
            )
        )
    return results


def check_timeline(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Manifest-only: vocal-on-vocal overlap (one vocal at a time) and
    layers that overrun the backbone bed."""
    name = "timeline"
    results: list[CheckResult] = []

    vocals = [(i, layer) for i, layer in enumerate(manifest.layers) if layer.role == "vocal"]
    overlaps: list[tuple[int, int, float]] = []
    for (i, a), (j, b) in itertools.combinations(vocals, 2):
        pairs = sorted([(a.place_at, a.out_end, i), (b.place_at, b.out_end, j)])
        overlap = pairs[0][1] - pairs[1][0]
        if overlap > cfg.vocal_overlap_tolerance_s:
            overlaps.append((i, j, overlap))
    if overlaps:
        worst = max(overlaps, key=lambda t: t[2])
        results.append(
            CheckResult(
                name,
                Status.FAIL,
                f"vocal layers {worst[0]} and {worst[1]} overlap "
                f"{worst[2]:.1f}s (> {cfg.vocal_overlap_tolerance_s}s) - "
                "one vocal at a time",
                {"overlaps": [{"a": a, "b": b, "overlap_s": s} for a, b, s in overlaps]},
            )
        )
    else:
        results.append(CheckResult(name, Status.PASS, "no vocal-on-vocal overlap", {}))

    # Layers must not overrun the bed (backbone) end.
    if m.backbone.exists and m.backbone.decoded_duration is not None:
        bed_end = m.backbone.decoded_duration
        for i, layer in enumerate(manifest.layers):
            if layer.out_end > bed_end + cfg.vocal_overlap_tolerance_s:
                results.append(
                    CheckResult(
                        name,
                        Status.FAIL,
                        f"layer {i} ({layer.source.name}) ends at "
                        f"{layer.out_end:.1f}s beyond the bed end {bed_end:.1f}s "
                        "- tail plays over silence",
                        {"layer": i, "layer_end_s": layer.out_end, "bed_end_s": bed_end},
                    )
                )
    return results


# ── post-render checks ───────────────────────────────────────────────


def check_output_duration(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Rendered output length should match the planned timeline end."""
    name = "output_duration"
    out = m.output
    if out is None or not out.exists or out.decoded_duration is None:
        return [_no_output(name, out)]

    expected = _expected_timeline_end(manifest, m)
    if expected is None:
        return [
            CheckResult(
                name,
                Status.WARN,
                "expected duration unavailable - output length unverified",
                {"actual_s": out.decoded_duration},
            )
        ]
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
            f"output {out.decoded_duration:.2f}s vs expected {expected:.2f}s "
            f"(Δ{delta:+.2f}s; warn {cfg.output_duration_warn_s:.1f}, "
            f"fail {cfg.output_duration_fail_s:.1f})",
            {
                "actual_s": out.decoded_duration,
                "expected_s": expected,
                "delta_s": delta,
            },
        )
    ]


def check_vocal_masking(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Vocal-band (200 Hz-4 kHz) level of the isolated vocal vs the bed
    in the same window - below threshold the vocal is buried."""
    name = "vocal_masking"
    has_vocals = any(layer.role == "vocal" for layer in manifest.layers)
    if not has_vocals:
        return [CheckResult(name, Status.PASS, "no vocal layers declared", {})]
    if not m.masking:
        return [
            CheckResult(
                name,
                Status.WARN,
                "vocal or backbone samples unavailable - masking unverified",
                {},
            )
        ]
    results: list[CheckResult] = []
    for item in m.masking:
        layer = manifest.layers[item.layer_index]
        margin = item.vocal_band_db - item.bed_band_db
        if margin < cfg.vocal_over_bed_fail_db:
            status = Status.FAIL
        elif margin < cfg.vocal_over_bed_warn_db:
            status = Status.WARN
        else:
            status = Status.PASS
        results.append(
            CheckResult(
                name,
                status,
                f"{layer.source.name}: vocal band {item.vocal_band_db:.1f} dB vs "
                f"bed {item.bed_band_db:.1f} dB (margin {margin:+.1f} dB vs "
                f"min {cfg.vocal_over_bed_fail_db:+.1f}) - "
                + ("vocal buried" if status is Status.FAIL else "audible"),
                {
                    "layer": item.layer_index,
                    "vocal_band_db": item.vocal_band_db,
                    "bed_band_db": item.bed_band_db,
                    "margin_db": margin,
                },
            )
        )
    return results


def check_level_jumps(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """RMS jump at declared segment boundaries in the rendered output."""
    name = "level_jumps"
    out = m.output
    if out is None or not out.exists or out.rms_times is None or out.rms_db is None:
        return [_no_output(name, out)]
    boundaries = sorted({t for layer in manifest.layers for t in (layer.place_at, layer.out_end)})
    worst: tuple[float, float] | None = None  # (boundary_t, jump_db)
    for t in boundaries:
        if t <= 0 or out.decoded_duration is None or t >= out.decoded_duration:
            continue
        before = _mean_rms(out, t - cfg.boundary_window_s, t)
        after = _mean_rms(out, t, t + cfg.boundary_window_s)
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
            f"worst boundary jump {worst[1]:.1f} dB at {worst[0]:.1f}s "
            f"(vs {cfg.level_jump_db:.0f} dB)",
            {"boundary_s": worst[0], "jump_db": worst[1]},
        )
    ]


def check_clipping(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    name = "clipping"
    out = m.output
    if out is None or not out.exists:
        return [_no_output(name, out)]
    if out.max_volume is None and out.sample_peak_db is None:
        return [CheckResult(name, Status.WARN, "no peak measurement available", {})]
    measured_peak = max(v for v in (out.max_volume, out.sample_peak_db) if v is not None)
    clipped_samples = out.clipped_sample_count
    status = (
        Status.FAIL if measured_peak >= cfg.clipping_dbfs or clipped_samples > 0 else Status.PASS
    )
    msg = f"peak {measured_peak:.1f} dBFS, clipped samples {clipped_samples} (vs {cfg.clipping_dbfs} dBFS)"
    if out.first_clip_time is not None:
        msg += f"; first clip at {out.first_clip_time:.0f}s"
    return [
        CheckResult(
            name,
            status,
            msg,
            {
                "max_volume_db": out.max_volume,
                "sample_peak_db": out.sample_peak_db,
                "clipped_sample_count": clipped_samples,
                "first_clip_time_s": out.first_clip_time,
            },
        )
    ]


def check_dropouts(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Near-silent windows in the rendered output not declared in the plan."""
    name = "dropouts"
    out = m.output
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
                f"{len(dropouts)} silent window(s) >= {cfg.dropout_min_s}s "
                f"(RMS < {cfg.dropout_rms_db:.0f} dB), first at "
                f"{first[0]:.1f}-{first[1]:.1f}s",
                {"dropouts": [{"start_s": a, "end_s": b} for a, b in dropouts]},
            )
        ]
    return [
        CheckResult(
            name,
            Status.PASS,
            f"no silent windows >= {cfg.dropout_min_s}s below {cfg.dropout_rms_db:.0f} dB",
            {},
        )
    ]


def check_loudness_consistency(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Per-segment integrated LUFS spread across the rendered output."""
    name = "loudness_consistency"
    out = m.output
    if out is None or not out.exists:
        return [_no_output(name, out)]
    values = [(s, e, lufs) for s, e, lufs in out.segments if lufs is not None]
    if len(values) < 2:
        return [
            CheckResult(
                name,
                Status.PASS,
                "fewer than 2 measurable segments - spread not applicable",
                {"segments": len(values)},
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
            f"segment LUFS spread {spread:.1f} LU across {len(values)} segments "
            f"(vs warn {cfg.lufs_spread_warn_lu:.0f} / fail {cfg.lufs_spread_fail_lu:.0f} LU)",
            {
                "spread_lu": spread,
                "segments": [{"start_s": s, "end_s": e, "lufs": v} for s, e, v in values],
            },
        )
    ]


def check_low_band_holes(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Low-frequency holes where kick/bass disappear but the full mix is not silent."""
    name = "low_band_holes"
    out = m.output
    if out is None or not out.exists or out.low_rms_times is None or out.low_rms_db is None:
        return [_no_output(name, out)]
    values = out.low_rms_db
    if len(values) < 2:
        return [CheckResult(name, Status.PASS, "low-band series too short", {})]
    median = float(np.median(values))
    low = (values < median - cfg.low_band_drop_fail_db) & (values < cfg.low_band_floor_db)
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
                f"{len(holes)} low-band hole(s) ≥ {cfg.low_band_min_s:.1f}s; "
                f"median {median:.1f} dB, first {first[0]:.1f}-{first[1]:.1f}s",
                {
                    "median_low_db": median,
                    "holes": [{"start_s": a, "end_s": b} for a, b in holes],
                },
            )
        ]
    return [
        CheckResult(
            name,
            Status.PASS,
            f"no low-band holes ≥ {cfg.low_band_min_s:.1f}s below "
            f"median-{cfg.low_band_drop_fail_db:.0f} dB and {cfg.low_band_floor_db:.0f} dB",
            {"median_low_db": median},
        )
    ]


def check_stereo_balance(
    manifest: Manifest, m: Measurements, cfg: VerifyConfig
) -> list[CheckResult]:
    """Catch severe L/R imbalance and negative mono-compatibility correlation."""
    name = "stereo_balance"
    out = m.output
    if out is None or not out.exists:
        return [_no_output(name, out)]
    if out.channel_rms_db is None:
        return [CheckResult(name, Status.PASS, "mono output or stereo unavailable", {})]
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
            f"L/R RMS {left:.1f}/{right:.1f} dB (Δ{imbalance:.1f} dB), correlation {corr_text}",
            {
                "left_rms_db": left,
                "right_rms_db": right,
                "imbalance_db": imbalance,
                "correlation": corr,
            },
        )
    ]


# ── orchestration ────────────────────────────────────────────────────

PRE_RENDER_CHECKS = (
    check_honest_duration,
    check_bpm_reliability,
    check_tempo_ratio_sanity,
    check_phase_alignment,
    check_source_trim_bounds,
    check_boundary_alignment,
    check_timeline,
)
POST_RENDER_CHECKS = (
    check_output_duration,
    check_vocal_masking,
    check_level_jumps,
    check_clipping,
    check_dropouts,
    check_loudness_consistency,
    check_low_band_holes,
    check_stereo_balance,
)

# Standalone checks — run on any audio file without a manifest.
# These never access the manifest or source layers.


def check_file_bpm(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Detect overall BPM of the file (standalone mode)."""
    name = "file_bpm"
    out = m.output
    if out is None or not out.exists:
        return [_no_output(name, out)]
    if out.bpm is None or out.bpm <= 0:
        return [
            CheckResult(name, Status.WARN, "BPM undetectable from this file", {})
        ]
    return [
        CheckResult(
            name,
            Status.PASS,
            f"detected {out.bpm:.2f} BPM (confidence {out.bpm_confidence:.2f})",
            {"bpm": out.bpm, "confidence": out.bpm_confidence},
        )
    ]


# ── standalone-only checks ──────────────────────────────────────────


def check_dynamic_range(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Peak-to-average-RMS crest factor — over-compressed or falling apart."""
    name = "dynamic_range"
    out = m.output
    if out is None or not out.exists or out.crest_factor is None:
        return [_no_output(name, out)]
    v = out.crest_factor
    if v < cfg.crest_factor_fail_min or v > cfg.crest_factor_fail_max:
        status = Status.FAIL
    elif v < cfg.crest_factor_warn_min or v > cfg.crest_factor_warn_max:
        status = Status.WARN
    else:
        status = Status.PASS
    return [
        CheckResult(
            name,
            status,
            f"{v:.1f} dB dynamic range "
            f"(norm {cfg.crest_factor_warn_min:.0f}-{cfg.crest_factor_warn_max:.0f}, "
            f"fail <{cfg.crest_factor_fail_min:.0f} >{cfg.crest_factor_fail_max:.0f})",
            {"crest_factor_db": v},
        )
    ]


def check_spectral_balance(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Spectral energy distribution — low / mid / high bands."""
    name = "spectral_balance"
    out = m.output
    if out is None or not out.exists:
        return [_no_output(name, out)]

    results: list[CheckResult] = []

    # Low band
    if out.low_band_pct is not None:
        v = out.low_band_pct
        if v < cfg.low_band_fail_min or v > cfg.low_band_fail_max:
            status = Status.FAIL
        elif v < cfg.low_band_warn_min or v > cfg.low_band_warn_max:
            status = Status.WARN
        else:
            status = Status.PASS
        results.append(
            CheckResult(
                f"{name}:low",
                status,
                f"low-band energy {v:.1f}% "
                f"(norm {cfg.low_band_warn_min:.0f}-{cfg.low_band_warn_max:.0f}%)",
                {"low_band_pct": v},
            )
        )

    # Mid band mud
    if out.mid_band_pct is not None:
        v = out.mid_band_pct
        if v > cfg.mid_mud_fail:
            status = Status.FAIL
        elif v > cfg.mid_mud_warn:
            status = Status.WARN
        else:
            status = Status.PASS
        results.append(
            CheckResult(
                f"{name}:mid",
                status,
                f"mid-band energy {v:.1f}% "
                f"(warn >{cfg.mid_mud_warn:.0f}%, fail >{cfg.mid_mud_fail:.0f}%)",
                {"mid_band_pct": v},
            )
        )

    # High band
    if out.high_band_pct is not None:
        v = out.high_band_pct
        if v < cfg.high_band_fail:
            status = Status.FAIL
        elif v < cfg.high_band_warn:
            status = Status.WARN
        else:
            status = Status.PASS
        results.append(
            CheckResult(
                f"{name}:high",
                status,
                f"high-band energy {v:.2f}% "
                f"(warn <{cfg.high_band_warn:.2f}%, fail <{cfg.high_band_fail:.2f}%)",
                {"high_band_pct": v},
            )
        )

    if not results:
        results.append(CheckResult(name, Status.WARN, "spectral measurements unavailable", {}))
    return results


def check_low_end_mono(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Stereo correlation in the low band (< 150 Hz) — phase issues kill sub weight."""
    name = "low_end_mono"
    out = m.output
    if out is None or not out.exists or out.low_end_corr is None:
        return [_no_output(name, out)]
    v = out.low_end_corr
    if v < cfg.low_end_corr_fail:
        status = Status.FAIL
    elif v < cfg.low_end_corr_warn:
        status = Status.WARN
    else:
        status = Status.PASS
    return [
        CheckResult(
            name,
            status,
            f"low-end correlation {v:.2f} "
            f"(warn <{cfg.low_end_corr_warn:.1f}, fail <{cfg.low_end_corr_fail:.1f})",
            {"low_end_correlation": v},
        )
    ]


def check_loudness_target(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Integrated LUFS suitability for club/streaming."""
    name = "loudness_target"
    out = m.output
    if out is None or not out.exists:
        return [_no_output(name, out)]
    if not out.segments or out.segments[0][2] is None:
        return [CheckResult(name, Status.WARN, "LUFS measurement unavailable", {})]
    lufs = out.segments[0][2]
    if lufs > cfg.lufs_fail_high or lufs < cfg.lufs_fail_low:
        status = Status.FAIL
    elif lufs > cfg.lufs_warn_high or lufs < cfg.lufs_warn_low:
        status = Status.WARN
    else:
        status = Status.PASS
    return [
        CheckResult(
            name,
            status,
            f"integrated LUFS {lufs:.1f} "
            f"(norm {cfg.lufs_warn_low:.0f} to {cfg.lufs_warn_high:.0f}, "
            f"fail <{cfg.lufs_fail_low:.0f} >{cfg.lufs_fail_high:.0f})",
            {"integrated_lufs": lufs},
        )
    ]


# ── windowed / temporal checks ─────────────────────────────────────


def check_energy_range(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Max-to-min RMS range — how much the overall loudness varies."""
    name = "energy_range"
    out = m.output
    if out is None or not out.exists:
        return [_no_output(name, out)]
    if out.rms_db is not None and out.rms_times is not None and len(out.rms_db) > 0:
        rms = out.rms_db
        times = out.rms_times
        duration = out.decoded_duration or float(times[-1])
        mask = np.ones(len(rms), dtype=bool)
        if duration > cfg.energy_range_edge_guard_s * 2:
            mask = (times >= cfg.energy_range_edge_guard_s) & (
                times <= duration - cfg.energy_range_edge_guard_s
            )
        if not bool(np.any(mask)):
            mask = np.ones(len(rms), dtype=bool)
        active_rms = rms[mask]
        active_times = times[mask]
        v = float(np.max(active_rms) - np.min(active_rms))
        min_time = float(active_times[np.argmin(active_rms)])
        max_time = float(active_times[np.argmax(active_rms)])
    elif out.energy_range_db is not None:
        v = out.energy_range_db
        min_time = out.rms_min_time
        max_time = out.rms_max_time
    else:
        return [_no_output(name, out)]

    if v > cfg.energy_range_fail_db:
        status = Status.FAIL
    elif v > cfg.energy_range_warn_db:
        status = Status.WARN
    else:
        status = Status.PASS
    msg = (
        f"RMS spread {v:.1f} dB (warn >{cfg.energy_range_warn_db:.0f}, "
        f"fail >{cfg.energy_range_fail_db:.0f}; "
        f"ignoring first/last {cfg.energy_range_edge_guard_s:.0f}s)"
    )
    if min_time is not None and max_time is not None:
        msg += f"; quietest at {min_time:.0f}s, loudest at {max_time:.0f}s"
    return [
        CheckResult(
            name,
            status,
            msg,
            {
                "energy_range_db": v,
                "raw_energy_range_db": out.energy_range_db,
                "rms_min_time_s": min_time,
                "rms_max_time_s": max_time,
                "edge_guard_s": cfg.energy_range_edge_guard_s,
            },
        )
    ]


def check_energy_dips(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Abrupt loudness dips — likely transition problems / gain mismatches."""
    name = "energy_dips"
    out = m.output
    if out is None or not out.exists or out.decoded_duration is None:
        return [_no_output(name, out)]
    duration_min = out.decoded_duration / 60.0
    rate = out.energy_dip_count / duration_min if duration_min > 0 else 0.0
    if rate > cfg.energy_dips_fail_per_min:
        status = Status.FAIL
    elif rate > cfg.energy_dips_warn_per_min:
        status = Status.WARN
    else:
        status = Status.PASS
    msg = f"{out.energy_dip_count} energy dips ({rate:.1f}/min, " \
          f"warn >{cfg.energy_dips_warn_per_min:.0f}/min, fail >{cfg.energy_dips_fail_per_min:.0f}/min)"
    if out.energy_dip_times:
        first = out.energy_dip_times[0]
        msg += f"; first at {first[0]:.0f}s–{first[1]:.0f}s"
        if len(out.energy_dip_times) > 1:
            msg += f" +{len(out.energy_dip_times) - 1} more"
    return [
        CheckResult(
            name,
            status,
            msg,
            {"dip_count": out.energy_dip_count, "dip_rate_per_min": rate,
             "dip_times": out.energy_dip_times},
        )
    ]


def check_bpm_stability(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """BPM consistency across 30-second windows — tempo drift in a set."""
    name = "bpm_stability"
    out = m.output
    if out is None or not out.exists or out.bpm_stability is None:
        return [_no_output(name, out)]
    v = out.bpm_stability
    if v > cfg.bpm_stability_fail:
        status = Status.FAIL
    elif v > cfg.bpm_stability_warn:
        status = Status.WARN
    else:
        status = Status.PASS
    msg = f"BPM spread σ={v:.2f} (warn >{cfg.bpm_stability_warn:.0f}, fail >{cfg.bpm_stability_fail:.0f})"
    if out.bpm_windows and len(out.bpm_windows) > 1:
        bpms = [w[1] for w in out.bpm_windows if w[1] > 0]
        if bpms:
            msg += f"; range {min(bpms):.1f}–{max(bpms):.1f}"
            # Show drift extremes
            main = float(np.median(bpms))
            outliers = [(w[0], w[1]) for w in out.bpm_windows if w[1] > 0 and abs(w[1] - main) > v * 2]
            if outliers:
                worst = max(outliers, key=lambda x: abs(x[1] - main))
                msg += f"; max drift {worst[1]:.1f} at {worst[0]:.0f}s"
    return [
        CheckResult(
            name,
            status,
            msg,
            {"bpm_stability": v},
        )
    ]


def check_rms_jumps(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Abrupt RMS changes (>9 dB) between 3-second windows — rough transitions."""
    name = "rms_jumps"
    out = m.output
    if out is None or not out.exists or out.rms_jumps_per_min is None:
        return [_no_output(name, out)]
    v = out.rms_jumps_per_min
    if v > cfg.rms_jumps_fail:
        status = Status.FAIL
    elif v > cfg.rms_jumps_warn:
        status = Status.WARN
    else:
        status = Status.PASS
    msg = f"{v:.2f} abrupt RMS jumps/min (warn >{cfg.rms_jumps_warn:.1f}, fail >{cfg.rms_jumps_fail:.1f})"
    if out.rms_jump_times:
        counts = {"rise": 0, "drop": 0}
        for t, d in out.rms_jump_times:
            if d > 0:
                counts["rise"] += 1
            else:
                counts["drop"] += 1
        first = out.rms_jump_times[0]
        direction = "+" if first[1] > 0 else ""
        msg += f"; worst {direction}{abs(first[1]):.0f}dB at {first[0]:.0f}s"
        remaining = len(out.rms_jump_times) - 1
        if remaining > 0:
            rises = counts["rise"] - (1 if first[1] > 0 else 0)
            drops = counts["drop"] - (1 if first[1] < 0 else 0)
            parts = []
            if rises > 0:
                parts.append(f"{rises} rise")
            if drops > 0:
                parts.append(f"{drops} drop")
            msg += f" +{', '.join(parts)}"
    return [
        CheckResult(
            name,
            status,
            msg,
            {"rms_jumps_per_min": v, "jump_events": out.rms_jump_times},
        )
    ]


# ── standalone: kick & energy-flow ──────────────────────────────────


def check_kick_consistency(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Low-band drops while full mix plays — kick disappearing mid-track.

    In techno the kick is the rhythmic foundation. Short kickless pauses
    are expected in breakdowns, but sustained kick loss (especially
    multiple events) indicates a arrangement problem or gain staging
    issue in the transition.
    """
    name = "kick_consistency"
    out = m.output
    if out is None or not out.exists:
        return [_no_output(name, out)]
    if out.kick_drop_count == 0 or not out.kick_drop_events:
        return [CheckResult(name, Status.PASS, "no kick drop-outs detected", {})]

    events = out.kick_drop_events
    worst_dur = max(e[1] - e[0] for e in events)
    msg = f"{out.kick_drop_count} kick drop-out(s), longest {worst_dur:.0f}s"
    if events:
        first = events[0]
        msg += f"; first at {first[0]:.0f}s–{first[1]:.0f}s"
        if len(events) > 1:
            msg += f" +{len(events) - 1} more"

    if worst_dur > cfg.kick_drop_fail_s:
        status = Status.FAIL
    elif worst_dur > cfg.kick_drop_warn_s:
        status = Status.WARN
    else:
        status = Status.PASS

    return [
        CheckResult(
            name,
            status,
            msg,
            {
                "drop_count": out.kick_drop_count,
                "longest_s": worst_dur,
                "events": [{"start_s": e[0], "end_s": e[1]} for e in events],
            },
        )
    ]


def check_energy_slope(manifest: Manifest, m: Measurements, cfg: VerifyConfig) -> list[CheckResult]:
    """Energy trend: negative slope means the mix is losing steam.

    A flat or slightly positive slope is normal for techno. Strongly
    negative means every segment is quieter than the last.
    """
    name = "energy_slope"
    out = m.output
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
    msg = (
        f"energy trend {direction}{v:.2f} dB/min "
        f"(warn <{cfg.energy_slope_warn:.1f}, fail <{cfg.energy_slope_fail:.1f} dB/min)"
    )
    if status is not Status.PASS:
        msg += " — mix declining in energy"
    return [
        CheckResult(
            name,
            status,
            msg,
            {"energy_slope_db_per_min": v},
        )
    ]


STANDALONE_CHECKS = (
    check_file_bpm,
    check_dynamic_range,
    check_spectral_balance,
    check_low_end_mono,
    check_loudness_target,
    check_energy_range,
    check_energy_dips,
    check_bpm_stability,
    check_rms_jumps,
    check_kick_consistency,
    check_energy_slope,
    check_clipping,
    check_dropouts,
    check_low_band_holes,
    check_stereo_balance,
)


def run_all_checks(
    manifest: Manifest | None,
    measurements: Measurements,
    config: VerifyConfig | None = None,
    *,
    skip_post: bool = False,
    checks_override: tuple[Any, ...] | None = None,
) -> list[CheckResult]:
    cfg = config or VerifyConfig()
    if checks_override is not None:
        checks = checks_override
    else:
        checks = PRE_RENDER_CHECKS if skip_post else PRE_RENDER_CHECKS + POST_RENDER_CHECKS
    results: list[CheckResult] = []
    for check in checks:
        results.extend(check(manifest, measurements, cfg))
    return results


# ── helpers ──────────────────────────────────────────────────────────


def _bpm_delta(a: float, b: float) -> float:
    """Min BPM distance over direct / double / half time."""
    return min(abs(a - b), abs(a * 2 - b), abs(a / 2 - b))


def _placed_beats(layer: Layer, beat_times: np.ndarray) -> np.ndarray:
    """Map source-time beats of a layer onto the output timeline."""
    beats = np.asarray(beat_times, dtype=np.float64)
    inside = beats[(beats >= layer.src_trim[0]) & (beats <= layer.src_trim[1])]
    return layer.place_at + (inside - layer.src_trim[0]) / layer.tempo_ratio


def _mean_rms(out: Any, start: float, end: float) -> float | None:
    mask = (out.rms_times >= start) & (out.rms_times < end)
    if not np.any(mask):
        return None
    return float(np.mean(out.rms_db[mask]))


def _expected_timeline_end(manifest: Manifest, m: Measurements) -> float | None:
    ends = [layer.out_end for layer in manifest.layers]
    if m.backbone.exists and m.backbone.decoded_duration is not None:
        ends.append(m.backbone.decoded_duration)
    return max(ends) if ends else None


def _nearest_delta_fraction(value: float, grid: np.ndarray, beat_period: float) -> float:
    if len(grid) == 0:
        return 0.0
    delta = float(np.min(np.abs(grid - value)))
    return delta / beat_period


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
