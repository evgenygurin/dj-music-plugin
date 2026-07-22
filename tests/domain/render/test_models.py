# tests/domain/render/test_models.py
from app.domain.render.models import (
    BeatgridEntry,
    RenderMode,
    RenderPlan,
    TrackInput,
    TrackSegment,
)


def test_track_input_roundtrip() -> None:
    ti = TrackInput(
        track_id=5435,
        yandex_id=49353955,
        title="Edit Select - Vault 2015",
        bpm=130.0,
        key_code=13,
        mix_in_ms=0,
        integrated_lufs=-12.33,
        file_path="/tmp/dj_audio/01 - x [49353955].mp3",
    )
    assert ti.tempo_ratio(130.0) == 1.0


def test_beatgrid_entry_effective_trim() -> None:
    e = BeatgridEntry(
        track_id=1, trim_start_s=0.4, refined_trim_s=0.42, gain_db=1.5, phase_ms=20.0
    )
    assert e.effective_trim == 0.42
    e2 = BeatgridEntry(
        track_id=1, trim_start_s=0.4, refined_trim_s=None, gain_db=0.0, phase_ms=0.0
    )
    assert e2.effective_trim == 0.4


def test_render_plan_holds_segments() -> None:
    seg = TrackSegment(
        index=0,
        track_id=1,
        file_path="/x.mp3",
        tempo_ratio=1.0,
        trim_start_s=0.4,
        gain_db=0.0,
        body_bars=24,
        d_in_s=0.0,
        d_out_s=59.0,
        length_s=103.0,
        start_s=0.0,
    )
    plan = RenderPlan(
        target_bpm=130.0,
        xsplit_low_hz=250,
        xsplit_high_hz=4000,
        eq_phase_1_ratio=0.40,
        eq_phase_2_ratio=0.70,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=0.85,
        segments=[seg],
    )
    assert plan.segments[0].index == 0
    assert plan.n == 1


def test_render_plan_carries_mode() -> None:
    seg = TrackSegment(
        index=0,
        track_id=1,
        file_path="/x.mp3",
        tempo_ratio=1.0,
        trim_start_s=0.4,
        gain_db=0.0,
        body_bars=24,
        d_in_s=0.0,
        d_out_s=59.0,
        length_s=103.0,
        start_s=0.0,
    )
    plan = RenderPlan(
        mode=RenderMode.CLASSIC,
        target_bpm=130.0,
        xsplit_low_hz=250,
        xsplit_high_hz=4000,
        eq_phase_1_ratio=0.40,
        eq_phase_2_ratio=0.70,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=0.85,
        segments=[seg],
    )
    assert plan.mode is RenderMode.CLASSIC


def test_render_package_exports_resolvable() -> None:
    import app.domain.render as r

    assert r.__all__ == [
        "STEM_ORDER",
        "STEM_VOICING",
        "BarPlan",
        "BarPlanner",
        "BeatgridEntry",
        "BeatgridIO",
        "BeatgridLimits",
        "ClassicSegmentFactory",
        "EffectPresetResolver",
        "RenderMode",
        "RenderPlan",
        "RenderPlanner",
        "RenderRequest",
        "RenderStrategy",
        "ResolvedEffects",
        "SegmentFactory",
        "SegmentGeometry",
        "StemSegment",
        "StemSegmentFactory",
        "StemVoicing",
        "TimelineWindows",
        "TrackInput",
        "TrackSegment",
        "TransitionWindow",
        "build_ffmpeg_cmd",
        "build_filtergraph",
        "build_stem_filtergraph",
        "clamp_entry",
        "entry_flags",
        "entry_from_row",
        "entry_to_row",
        "gains_to_median",
        "place_segments",
        "run_render",
        "select_strategy",
        "timeline_windows",
    ]
    for name in r.__all__:
        assert hasattr(r, name), f"missing export: {name}"
