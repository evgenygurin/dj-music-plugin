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
