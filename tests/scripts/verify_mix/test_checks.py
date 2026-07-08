"""Each check must both fire on a bad input and pass on a good one.

Pure unit tests: measurements are fabricated, no audio or ffmpeg here.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np

from scripts.verify_mix.analysis import (
    LayerMasking,
    Measurements,
    OutputMeasure,
    SourceMeasure,
)
from scripts.verify_mix.checks import (
    Status,
    VerifyConfig,
    check_boundary_alignment,
    check_bpm_reliability,
    check_clipping,
    check_dropouts,
    check_energy_range,
    check_honest_duration,
    check_level_jumps,
    check_loudness_consistency,
    check_low_band_holes,
    check_output_duration,
    check_phase_alignment,
    check_source_trim_bounds,
    check_stereo_balance,
    check_tempo_ratio_sanity,
    check_timeline,
    check_vocal_masking,
    run_all_checks,
)
from scripts.verify_mix.manifest import Backbone, Layer, Manifest

CFG = VerifyConfig()


def _manifest(layers: tuple[Layer, ...] = (), bpm: float = 124.0) -> Manifest:
    return Manifest(
        output=Path("mix.mp3"),
        backbone=Backbone(source=Path("backbone.wav"), bpm=bpm),
        layers=layers,
        base_dir=Path("/work"),
    )


def _src(
    name: str = "backbone.wav",
    *,
    decoded: float = 133.0,
    probe: float = 133.2,
    bpm: float = 124.0,
    conf: float = 0.6,
    beats_bpm: float | None = None,
    beats_offset: float = 0.0,
) -> SourceMeasure:
    period = 60.0 / (beats_bpm or bpm)
    return SourceMeasure(
        path=Path(f"/work/{name}"),
        exists=True,
        decoded_duration=decoded,
        ffprobe_dur=probe,
        bpm=bpm,
        bpm_confidence=conf,
        beat_times=np.arange(0.0, decoded, period) + beats_offset,
    )


def _layer(
    role: str = "bed",
    *,
    trim: tuple[float, float] = (0.0, 30.0),
    ratio: float = 1.0,
    place_at: float = 0.0,
    gain: float = 1.0,
    name: str = "layer.wav",
) -> Layer:
    return Layer(
        source=Path(name),
        role=role,
        src_trim=trim,
        tempo_ratio=ratio,
        place_at=place_at,
        gain=gain,
    )


# ── honest_duration ──────────────────────────────────────────────────


def test_honest_duration_fails_on_ffprobe_lie() -> None:
    # the Suno streamed-mp3 case: ffprobe says 223 s, decode says 133 s
    m = Measurements(backbone=_src(decoded=133.0, probe=223.0))

    results = check_honest_duration(_manifest(), m, CFG)

    assert results[0].status is Status.FAIL


def test_honest_duration_passes_on_close_durations() -> None:
    m = Measurements(backbone=_src(decoded=133.0, probe=133.5))

    results = check_honest_duration(_manifest(), m, CFG)

    assert results[0].status is Status.PASS


def test_honest_duration_warns_on_missing_source() -> None:
    m = Measurements(backbone=SourceMeasure(path=Path("/work/gone.wav")))

    results = check_honest_duration(_manifest(), m, CFG)

    assert results[0].status is Status.WARN


# ── bpm_reliability ──────────────────────────────────────────────────


def test_bpm_reliability_fails_on_declared_mismatch() -> None:
    m = Measurements(backbone=_src(bpm=137.0))

    results = check_bpm_reliability(_manifest(bpm=124.0), m, CFG)

    assert results[0].status is Status.FAIL


def test_bpm_reliability_warns_on_low_confidence() -> None:
    m = Measurements(backbone=_src(bpm=124.1, conf=0.05))

    results = check_bpm_reliability(_manifest(bpm=124.0), m, CFG)

    assert results[0].status is Status.WARN


def test_bpm_reliability_passes_on_confident_match() -> None:
    m = Measurements(backbone=_src(bpm=124.2, conf=0.6))

    results = check_bpm_reliability(_manifest(bpm=124.0), m, CFG)

    assert results[0].status is Status.PASS


def test_bpm_reliability_accepts_half_time_detection() -> None:
    # detector locked to half tempo — not a declared-BPM lie
    m = Measurements(backbone=_src(bpm=62.0, conf=0.6))

    results = check_bpm_reliability(_manifest(bpm=124.0), m, CFG)

    assert results[0].status is Status.PASS


# ── tempo_ratio_sanity ───────────────────────────────────────────────


def test_tempo_ratio_fails_on_bed_layer_mismatch() -> None:
    layer = _layer("bed", ratio=1.0)
    m = Measurements(backbone=_src(), layers={0: _src("layer.wav", bpm=137.0)})

    results = check_tempo_ratio_sanity(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.FAIL
    assert "137.00" in results[0].message


def test_tempo_ratio_only_warns_on_vocal_layer_mismatch() -> None:
    layer = _layer("vocal", ratio=1.0)
    m = Measurements(backbone=_src(), layers={0: _src("layer.wav", bpm=137.0)})

    results = check_tempo_ratio_sanity(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.WARN


def test_tempo_ratio_passes_on_correct_ratio() -> None:
    # 118 BPM source stretched by 124/118 lands on the backbone tempo
    layer = _layer("bed", ratio=124.0 / 118.0)
    m = Measurements(backbone=_src(), layers={0: _src("layer.wav", bpm=118.0)})

    results = check_tempo_ratio_sanity(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.PASS


def test_tempo_ratio_warns_on_unreliable_layer_bpm() -> None:
    layer = _layer("bed")
    m = Measurements(backbone=_src(), layers={0: _src("layer.wav", bpm=124.0, conf=0.01)})

    results = check_tempo_ratio_sanity(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.WARN


# ── phase_alignment ──────────────────────────────────────────────────


def test_phase_alignment_passes_on_grid() -> None:
    layer = _layer("bed", trim=(0.0, 30.0), place_at=0.0)
    m = Measurements(
        backbone=_src(decoded=60.0),
        layers={0: _src("layer.wav", decoded=30.0)},
    )

    results = check_phase_alignment(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.PASS


def test_phase_alignment_fails_on_half_beat_offset_bed() -> None:
    period = 60.0 / 124.0
    layer = _layer("bed", trim=(0.0, 30.0), place_at=period / 2)
    m = Measurements(
        backbone=_src(decoded=60.0),
        layers={0: _src("layer.wav", decoded=30.0)},
    )

    results = check_phase_alignment(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.FAIL


def test_phase_alignment_only_warns_for_vocal() -> None:
    period = 60.0 / 124.0
    layer = _layer("vocal", trim=(0.0, 30.0), place_at=period / 2)
    m = Measurements(
        backbone=_src(decoded=60.0),
        layers={0: _src("layer.wav", decoded=30.0)},
    )

    results = check_phase_alignment(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.WARN


def test_phase_alignment_warns_without_backbone_grid() -> None:
    m = Measurements(backbone=SourceMeasure(path=Path("/work/backbone.wav")))

    results = check_phase_alignment(_manifest((_layer(),)), m, CFG)

    assert results[0].status is Status.WARN


# ── source_trim_bounds ───────────────────────────────────────────────


def test_source_trim_bounds_fails_when_trim_exceeds_source() -> None:
    layer = _layer("bed", trim=(0.0, 35.0))
    m = Measurements(backbone=_src(), layers={0: _src("layer.wav", decoded=30.0)})

    results = check_source_trim_bounds(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.FAIL


def test_source_trim_bounds_passes_when_trim_fits() -> None:
    layer = _layer("bed", trim=(2.0, 30.0))
    m = Measurements(backbone=_src(), layers={0: _src("layer.wav", decoded=30.0)})

    results = check_source_trim_bounds(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.PASS


# ── boundary_alignment ───────────────────────────────────────────────


def test_boundary_alignment_fails_bed_off_beat() -> None:
    period = 60.0 / 124.0
    layer = _layer("bed", trim=(0.0, 30.0), place_at=period / 2)
    m = Measurements(
        backbone=_src(decoded=60.0),
        layers={0: _src("layer.wav", decoded=30.0)},
    )

    results = check_boundary_alignment(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.FAIL


def test_boundary_alignment_warns_on_off_bar_boundary() -> None:
    period = 60.0 / 124.0
    layer = _layer("vocal", trim=(0.0, 16 * period), place_at=period)
    m = Measurements(
        backbone=_src(decoded=60.0),
        layers={0: _src("layer.wav", decoded=30.0)},
    )

    results = check_boundary_alignment(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.WARN


def test_boundary_alignment_passes_on_bar_grid() -> None:
    period = 60.0 / 124.0
    layer = _layer("bed", trim=(0.0, 16 * period), place_at=4 * period)
    m = Measurements(
        backbone=_src(decoded=60.0),
        layers={0: _src("layer.wav", decoded=30.0)},
    )

    results = check_boundary_alignment(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.PASS


# ── timeline ─────────────────────────────────────────────────────────


def test_timeline_fails_on_vocal_overlap() -> None:
    a = _layer("vocal", trim=(0.0, 30.0), place_at=0.0, name="a.wav")
    b = _layer("vocal", trim=(0.0, 30.0), place_at=20.0, name="b.wav")
    m = Measurements(backbone=_src(decoded=120.0))

    results = check_timeline(_manifest((a, b)), m, CFG)

    assert any(r.status is Status.FAIL and "overlap" in r.message for r in results)


def test_timeline_finds_non_adjacent_vocal_overlap() -> None:
    a = _layer("vocal", trim=(0.0, 30.0), place_at=0.0, name="a.wav")
    b = _layer("vocal", trim=(0.0, 5.0), place_at=40.0, name="b.wav")
    c = _layer("vocal", trim=(0.0, 30.0), place_at=20.0, name="c.wav")
    m = Measurements(backbone=_src(decoded=120.0))

    results = check_timeline(_manifest((a, b, c)), m, CFG)

    assert any(r.status is Status.FAIL and "overlap" in r.message for r in results)


def test_timeline_passes_on_sequential_vocals() -> None:
    a = _layer("vocal", trim=(0.0, 30.0), place_at=0.0, name="a.wav")
    b = _layer("vocal", trim=(0.0, 30.0), place_at=31.0, name="b.wav")
    m = Measurements(backbone=_src(decoded=120.0))

    results = check_timeline(_manifest((a, b)), m, CFG)

    assert all(r.status is Status.PASS for r in results)


def test_timeline_fails_on_layer_beyond_bed_end() -> None:
    layer = _layer("vocal", trim=(0.0, 50.0), place_at=100.0)
    m = Measurements(backbone=_src(decoded=120.0))

    results = check_timeline(_manifest((layer,)), m, CFG)

    assert any(r.status is Status.FAIL and "beyond" in r.message for r in results)


# ── vocal_masking ────────────────────────────────────────────────────


def test_vocal_masking_fails_when_buried() -> None:
    layer = _layer("vocal")
    m = Measurements(
        backbone=_src(),
        masking=[LayerMasking(layer_index=0, vocal_band_db=-30.0, bed_band_db=-20.0)],
    )

    results = check_vocal_masking(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.FAIL
    assert "buried" in results[0].message


def test_vocal_masking_warns_in_grey_zone() -> None:
    layer = _layer("vocal")
    m = Measurements(
        backbone=_src(),
        masking=[LayerMasking(layer_index=0, vocal_band_db=-21.0, bed_band_db=-20.0)],
    )

    results = check_vocal_masking(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.WARN


def test_vocal_masking_passes_when_vocal_on_top() -> None:
    layer = _layer("vocal")
    m = Measurements(
        backbone=_src(),
        masking=[LayerMasking(layer_index=0, vocal_band_db=-15.0, bed_band_db=-20.0)],
    )

    results = check_vocal_masking(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.PASS


def test_vocal_masking_passes_without_vocals() -> None:
    results = check_vocal_masking(_manifest(), Measurements(backbone=_src()), CFG)

    assert results[0].status is Status.PASS


def test_vocal_masking_warns_when_unmeasurable() -> None:
    layer = _layer("vocal")
    m = Measurements(backbone=SourceMeasure(path=Path("/work/backbone.wav")))

    results = check_vocal_masking(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.WARN


# ── level_jumps ──────────────────────────────────────────────────────


def _output(
    rms_db: np.ndarray,
    *,
    hop: float = 0.2,
    max_volume: float = -1.0,
    sample_peak: float | None = -1.0,
    clipped_samples: int = 0,
    low_rms_db: np.ndarray | None = None,
    low_hop: float = 1.0,
    channel_rms_db: tuple[float, float] | None = (-18.0, -18.2),
    stereo_correlation: float | None = 0.8,
    segments: Sequence[tuple[float, float, float | None]] | None = None,
) -> OutputMeasure:
    times = np.arange(len(rms_db)) * hop + hop / 2
    low = low_rms_db if low_rms_db is not None else np.full(max(2, len(rms_db) // 5), -24.0)
    low_times = np.arange(len(low)) * low_hop + low_hop / 2
    return OutputMeasure(
        path=Path("/work/mix.mp3"),
        exists=True,
        decoded_duration=float(len(rms_db) * hop),
        rms_times=times,
        rms_db=rms_db,
        low_rms_times=low_times,
        low_rms_db=low,
        max_volume=max_volume,
        sample_peak_db=sample_peak,
        clipped_sample_count=clipped_samples,
        channel_rms_db=channel_rms_db,
        stereo_correlation=stereo_correlation,
        segments=list(segments or []),
    )


# ── output_duration ──────────────────────────────────────────────────


def test_output_duration_fails_on_truncated_render() -> None:
    out = _output(np.full(500, -18.0))  # 100 s
    m = Measurements(backbone=_src(decoded=120.0), output=out)

    results = check_output_duration(_manifest(), m, CFG)

    assert results[0].status is Status.FAIL


def test_output_duration_passes_when_expected_length_matches() -> None:
    out = _output(np.full(600, -18.0))  # 120 s
    m = Measurements(backbone=_src(decoded=120.0), output=out)

    results = check_output_duration(_manifest(), m, CFG)

    assert results[0].status is Status.PASS


def test_level_jumps_fails_on_step() -> None:
    # boundary at 10 s, 12 dB step
    layer = _layer("bed", trim=(0.0, 10.0), place_at=0.0)
    rms = np.full(100, -18.0)
    rms[50:] = -30.0
    m = Measurements(backbone=_src(), output=_output(rms))

    results = check_level_jumps(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.FAIL


def test_energy_range_ignores_terminal_fade_guard() -> None:
    rms = np.full(120, -12.0)
    rms[20] = -9.0
    rms[-4:] = np.array([-24.0, -38.0, -56.0, -41.0])
    out = _output(rms)
    out.energy_range_db = float(np.max(rms) - np.min(rms))
    out.rms_min_time = float(out.rms_times[np.argmin(rms)])
    out.rms_max_time = float(out.rms_times[np.argmax(rms)])
    m = Measurements(backbone=_src(), output=out)

    results = check_energy_range(None, m, CFG)

    assert results[0].status is Status.PASS
    assert results[0].detail["raw_energy_range_db"] > CFG.energy_range_fail_db
    assert results[0].detail["energy_range_db"] < CFG.energy_range_warn_db


def test_level_jumps_passes_on_smooth_mix() -> None:
    layer = _layer("bed", trim=(0.0, 10.0), place_at=0.0)
    rms = np.full(100, -18.0)
    m = Measurements(backbone=_src(), output=_output(rms))

    results = check_level_jumps(_manifest((layer,)), m, CFG)

    assert results[0].status is Status.PASS


def test_level_jumps_warns_without_output() -> None:
    results = check_level_jumps(_manifest((_layer(),)), Measurements(backbone=_src()), CFG)

    assert results[0].status is Status.WARN


# ── clipping ─────────────────────────────────────────────────────────


def test_clipping_fails_at_full_scale() -> None:
    m = Measurements(backbone=_src(), output=_output(np.full(50, -18.0), max_volume=0.0))

    results = check_clipping(_manifest(), m, CFG)

    assert results[0].status is Status.FAIL


def test_clipping_passes_with_headroom() -> None:
    m = Measurements(backbone=_src(), output=_output(np.full(50, -18.0), max_volume=-1.0))

    results = check_clipping(_manifest(), m, CFG)

    assert results[0].status is Status.PASS


def test_clipping_fails_on_sample_clips_even_when_volumedetect_misses() -> None:
    m = Measurements(
        backbone=_src(),
        output=_output(
            np.full(50, -18.0),
            max_volume=-0.5,
            sample_peak=0.0,
            clipped_samples=12,
        ),
    )

    results = check_clipping(_manifest(), m, CFG)

    assert results[0].status is Status.FAIL


# ── dropouts ─────────────────────────────────────────────────────────


def test_dropouts_fails_on_silent_hole() -> None:
    rms = np.full(100, -18.0)
    rms[40:45] = -80.0  # 1 s of near-silence
    m = Measurements(backbone=_src(), output=_output(rms))

    results = check_dropouts(_manifest(), m, CFG)

    assert results[0].status is Status.FAIL


def test_dropouts_passes_on_continuous_signal() -> None:
    m = Measurements(backbone=_src(), output=_output(np.full(100, -18.0)))

    results = check_dropouts(_manifest(), m, CFG)

    assert results[0].status is Status.PASS


def test_dropouts_ignores_sub_threshold_blip() -> None:
    rms = np.full(100, -18.0)
    rms[40] = -80.0  # single 0.2 s window < dropout_min_s
    m = Measurements(backbone=_src(), output=_output(rms))

    results = check_dropouts(_manifest(), m, CFG)

    assert results[0].status is Status.PASS


# ── loudness_consistency ─────────────────────────────────────────────


def test_loudness_fails_on_wide_spread() -> None:
    segments = [(0.0, 30.0, -12.0), (30.0, 60.0, -20.0)]
    m = Measurements(backbone=_src(), output=_output(np.full(50, -18.0), segments=segments))

    results = check_loudness_consistency(_manifest(), m, CFG)

    assert results[0].status is Status.FAIL


def test_loudness_warns_on_moderate_spread() -> None:
    segments = [(0.0, 30.0, -14.0), (30.0, 60.0, -18.0)]
    m = Measurements(backbone=_src(), output=_output(np.full(50, -18.0), segments=segments))

    results = check_loudness_consistency(_manifest(), m, CFG)

    assert results[0].status is Status.WARN


def test_loudness_passes_on_even_segments() -> None:
    segments = [(0.0, 30.0, -14.0), (30.0, 60.0, -14.8)]
    m = Measurements(backbone=_src(), output=_output(np.full(50, -18.0), segments=segments))

    results = check_loudness_consistency(_manifest(), m, CFG)

    assert results[0].status is Status.PASS


# ── low_band_holes ───────────────────────────────────────────────────


def test_low_band_holes_fails_on_bass_dropout() -> None:
    low = np.full(80, -24.0)
    low[20:27] = -50.0
    m = Measurements(backbone=_src(), output=_output(np.full(400, -18.0), low_rms_db=low))

    results = check_low_band_holes(_manifest(), m, CFG)

    assert results[0].status is Status.FAIL


def test_low_band_holes_passes_on_stable_low_end() -> None:
    low = np.full(80, -26.0)
    m = Measurements(backbone=_src(), output=_output(np.full(400, -18.0), low_rms_db=low))

    results = check_low_band_holes(_manifest(), m, CFG)

    assert results[0].status is Status.PASS


# ── stereo_balance ───────────────────────────────────────────────────


def test_stereo_balance_fails_on_severe_imbalance() -> None:
    out = _output(np.full(100, -18.0), channel_rms_db=(-12.0, -20.0), stereo_correlation=0.7)
    m = Measurements(backbone=_src(), output=out)

    results = check_stereo_balance(_manifest(), m, CFG)

    assert results[0].status is Status.FAIL


def test_stereo_balance_warns_on_negative_correlation() -> None:
    out = _output(np.full(100, -18.0), channel_rms_db=(-18.0, -18.2), stereo_correlation=-0.1)
    m = Measurements(backbone=_src(), output=out)

    results = check_stereo_balance(_manifest(), m, CFG)

    assert results[0].status is Status.WARN


def test_stereo_balance_passes_on_balanced_output() -> None:
    out = _output(np.full(100, -18.0), channel_rms_db=(-18.0, -18.1), stereo_correlation=0.8)
    m = Measurements(backbone=_src(), output=out)

    results = check_stereo_balance(_manifest(), m, CFG)

    assert results[0].status is Status.PASS


# ── run_all_checks ───────────────────────────────────────────────────


def test_run_all_checks_covers_full_battery() -> None:
    layer = _layer("vocal", trim=(0.0, 30.0), place_at=10.0)
    m = Measurements(
        backbone=_src(decoded=120.0),
        layers={0: _src("layer.wav", decoded=30.0)},
        masking=[LayerMasking(layer_index=0, vocal_band_db=-15.0, bed_band_db=-20.0)],
        output=_output(np.full(300, -18.0)),
    )

    results = run_all_checks(_manifest((layer,)), m)

    names = {r.name for r in results}
    assert names == {
        "honest_duration",
        "bpm_reliability",
        "tempo_ratio_sanity",
        "phase_alignment",
        "source_trim_bounds",
        "boundary_alignment",
        "timeline",
        "output_duration",
        "vocal_masking",
        "level_jumps",
        "clipping",
        "dropouts",
        "loudness_consistency",
        "low_band_holes",
        "stereo_balance",
    }


def test_run_all_checks_pre_only_skips_post_render() -> None:
    m = Measurements(backbone=_src())

    results = run_all_checks(_manifest(), m, skip_post=True)

    names = {r.name for r in results}
    assert "clipping" not in names
    assert "honest_duration" in names


def test_missing_everything_degrades_to_warn_not_crash() -> None:
    layer = _layer("vocal")
    m = Measurements(
        backbone=SourceMeasure(path=Path("/work/backbone.wav")),
        layers={0: SourceMeasure(path=Path("/work/layer.wav"))},
        output=OutputMeasure(path=Path("/work/mix.mp3")),
    )

    results = run_all_checks(_manifest((layer,)), m)

    assert results  # ran to completion
    assert all(r.status in (Status.WARN, Status.PASS) for r in results)
