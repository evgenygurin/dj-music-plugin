"""Stem-aware multi-deck filtergraph + plan builder."""

from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan
from app.domain.render.models import STEM_ORDER, BeatgridEntry, TrackInput
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest
from app.domain.render.runner import build_ffmpeg_cmd
from app.domain.render.stem_graph import build_stem_filtergraph

_STEMS = STEM_ORDER


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
    request = RenderRequest(
        version_id=1,
        workspace="/tmp/ws",
        timestamp="20260101",
        stem=True,
        body_bars=24,
        transition_bars=16,
    )
    bar_plan = BarPlan(
        transition_bars=tuple([16] * max(0, n - 1)),
        body_bars=[24] * n,
    )
    return RenderPlanner().assemble(
        RenderSettings(target_bpm=target_bpm),
        request,
        inputs,
        grid,
        bar_plan,
        stem_paths=stem_paths_by_track,
    )


def test_stem_plan_has_stem_segments_not_classic():
    plan = _stem_plan(3)
    assert plan.stem_segments is not None
    assert plan.segments == []
    assert plan.n == 3
    seg = plan.stem_segments[0]
    assert set(seg.stem_paths) == set(_STEMS)


def test_stem_filtergraph_shape_all_five_stems():
    parts = build_stem_filtergraph(_stem_plan(1))
    joined = ";".join(parts)
    for stem in _STEMS:
        assert f"[s0_{stem}]" in joined
        assert f"[s0_{stem}_faded]" in joined
    # 5 stems recombined per track, straight sum (no averaging)
    assert "amix=inputs=5:normalize=0" in joined
    # master chain
    assert "firequalizer" in joined
    assert "alimiter=level_in=1:level_out=1:limit=0.85" in joined
    assert joined.endswith("[mix]")


def test_stem_filtergraph_artifact_masking_hpf():
    joined = ";".join(build_stem_filtergraph(_stem_plan(1)))
    # harmonic/instrumental/acappella get bleed-masking high-pass; drums + bass stay full-range
    assert "highpass=f=120" in joined  # instrumental + acappella
    assert "highpass=f=80" in joined  # harmonic
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
    assert len(fade_lines) == 5
    # every stem of the final track carries an out-fade
    assert all("afade=t=out" in p for p in fade_lines)


def test_stem_filtergraph_is_deterministic():
    assert build_stem_filtergraph(_stem_plan(3)) == build_stem_filtergraph(_stem_plan(3))


def test_stem_filtergraph_keeps_instrumental_as_quiet_safety_bed():
    joined = ";".join(build_stem_filtergraph(_stem_plan(1)))
    assert "[s0_instrumental]" in joined
    assert "volume=-7.00dB" in joined


def test_runner_stem_branch_maps_five_inputs_per_track():
    plan = _stem_plan(2)
    cmd = build_ffmpeg_cmd(plan, "/tmp/out.mp3")
    # 2 tracks x 5 stems = 10 inputs, in (track, stem) order
    inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
    assert inputs == [
        "/stems/0/drums.flac",
        "/stems/0/bass.flac",
        "/stems/0/harmonic.flac",
        "/stems/0/instrumental.flac",
        "/stems/0/acappella.flac",
        "/stems/1/drums.flac",
        "/stems/1/bass.flac",
        "/stems/1/harmonic.flac",
        "/stems/1/instrumental.flac",
        "/stems/1/acappella.flac",
    ]
    assert "[mix]" in cmd
