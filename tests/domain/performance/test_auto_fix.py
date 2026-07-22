from __future__ import annotations

from app.domain.performance.auto_fix import AutoFixPlan, Defect, DefectType


def test_ffmpeg_fix_chain_returns_argv_not_shell_string() -> None:
    plan = AutoFixPlan(
        defects=[Defect(DefectType.DROPOUT, start_s=1.0, end_s=2.0, severity=0.5)],
        original_path="unused",
    )

    args = plan.ffmpeg_fix_chain("mix'; touch /tmp/pwn #.mp3", "fixed.mp3")

    assert isinstance(args, list)
    assert args[:3] == ["ffmpeg", "-i", "mix'; touch /tmp/pwn #.mp3"]
    assert args[-1] == "fixed.mp3"


def test_bass_thin_scopes_every_equalizer_to_defect_window() -> None:
    plan = AutoFixPlan(
        defects=[Defect(DefectType.BASS_THIN, start_s=10.0, end_s=14.0, severity=0.5)],
        original_path="unused",
    )

    args = plan.ffmpeg_fix_chain("mix.mp3", "fixed.mp3")
    filter_arg = args[args.index("-af") + 1]

    assert filter_arg.count("equalizer=") == 2
    assert filter_arg.count("enable='between(t,10.000,14.000)'") == 2
