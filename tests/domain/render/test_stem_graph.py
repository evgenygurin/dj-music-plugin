"""Stem-aware multi-deck filtergraph + plan builder."""

from app.audio.render.runner import build_ffmpeg_cmd
from app.domain.render.models import BeatgridEntry, TrackInput
from app.domain.render.stem_graph import build_stem_filtergraph
from app.domain.render.timeline import build_stem_render_plan

_STEMS = ("drums", "bass", "vocals", "other")


def _stem_plan(n: int, *, target_bpm: float = 130.0):
    inputs = [
        TrackInput(
            track_id=i,
            yandex_id=i,
            title=f"t{i}",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path=f"/x{i}.mp3",
            duration_ms=600_000,
        )
        for i in range(n)
    ]
    stem_paths_by_track = {i: {s: f"/stems/{i}/{s}.flac" for s in _STEMS} for i in range(n)}
    grid = {
        i: BeatgridEntry(
            track_id=i, trim_start_s=0.4, refined_trim_s=0.4, gain_db=0.0, phase_ms=0.0
        )
        for i in range(n)
    }
    return build_stem_render_plan(
        inputs,
        stem_paths_by_track,
        grid,
        target_bpm=target_bpm,
        body_bars=24,
        transition_bars=16,
        xsplit_low_hz=250,
        xsplit_high_hz=4000,
        eq_phase_1_ratio=0.40,
        eq_phase_2_ratio=0.70,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=0.85,
    )


def test_stem_plan_has_stem_segments_not_classic():
    plan = _stem_plan(3)
    assert plan.stem_segments is not None
    assert plan.segments == []
    assert plan.n == 3
    seg = plan.stem_segments[0]
    assert set(seg.stem_paths) == set(_STEMS)


def test_stem_filtergraph_shape_all_four_stems():
    parts = build_stem_filtergraph(_stem_plan(1))
    joined = ";".join(parts)
    for stem in _STEMS:
        assert f"[s0_{stem}]" in joined
        assert f"[s0_{stem}_faded]" in joined
    # 4 stems recombined per track, straight sum (no averaging)
    assert "amix=inputs=4:normalize=0" in joined
    # master chain
    assert "firequalizer" in joined
    assert "alimiter=level_in=1:level_out=1:limit=0.85" in joined
    assert joined.endswith("[mix]")


def test_stem_filtergraph_artifact_masking_hpf():
    joined = ";".join(build_stem_filtergraph(_stem_plan(1)))
    # vocals + other get a bleed-masking high-pass; drums + bass stay full-range
    assert "highpass=f=120" in joined  # vocals
    assert "highpass=f=80" in joined  # other
    # the drums chain carries no highpass before its volume stage
    drums_chain = next(
        p for p in build_stem_filtergraph(_stem_plan(1)) if p.endswith("[s0_drums]")
    )
    assert "highpass" not in drums_chain


def test_stem_bass_is_pinpoint_swap_between_tracks():
    parts = build_stem_filtergraph(_stem_plan(2))
    joined = ";".join(parts)
    beat_s = 60.0 / 130.0
    # incoming bass on track 1 fades in over exactly one beat (clean swap)
    assert "[s1_bass]afade=t=in:curve=qsin" in joined
    assert f":d={beat_s:.3f}" in joined


def test_stem_last_track_fades_out_no_hard_cut():
    parts = build_stem_filtergraph(_stem_plan(2))
    fade_lines = [p for p in parts if any(p.startswith(f"[s1_{s}]") for s in _STEMS)]
    assert len(fade_lines) == 4
    # every stem of the final track carries an out-fade
    assert all("afade=t=out" in p for p in fade_lines)


def test_stem_filtergraph_is_deterministic():
    assert build_stem_filtergraph(_stem_plan(3)) == build_stem_filtergraph(_stem_plan(3))


def test_runner_stem_branch_maps_four_inputs_per_track():
    plan = _stem_plan(2)
    cmd = build_ffmpeg_cmd(plan, "/tmp/out.mp3")
    # 2 tracks x 4 stems = 8 inputs, in (track, stem) order
    inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
    assert inputs == [
        "/stems/0/drums.flac",
        "/stems/0/bass.flac",
        "/stems/0/vocals.flac",
        "/stems/0/other.flac",
        "/stems/1/drums.flac",
        "/stems/1/bass.flac",
        "/stems/1/vocals.flac",
        "/stems/1/other.flac",
    ]
    assert "[mix]" in cmd
