"""AutoFixRender — automatic repair of render diagnostics defects.

After render_diagnose finds defects (level jumps, dropouts, bass-thin,
phase issues, entry shocks, low-end collapse), this module generates
corrective ffmpeg filter graphs to fix them automatically.

Fix strategies:
  LEVEL-JUMP: smooth volume adjustment at the jump point (compand unsupported
    with timeline enables in FFmpeg 8)
  DROPOUT: apply makeup gain (+3-6 dB) at the dropout
  BASS-THIN: boost sub-bass (60-120 Hz) during affected window
  PHASE-UNSTABLE: apply mid-side processing to widen stereo safely
  ENTRY-SHOCK: apply short fade-in (100-500 ms)
  LOW-END-COLLAPSE: EQ boost + volume makeup on low band
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DefectType(Enum):
    LEVEL_JUMP = "LEVEL-JUMP"
    DROPOUT = "DROPOUT"
    BASS_THIN = "bass-thin"
    PHASE_UNSTABLE = "PHASE-UNSTABLE"
    ENTRY_SHOCK = "ENTRY-SHOCK"
    LOW_END_COLLAPSE = "LOW-END-COLLAPSE"


@dataclass
class Defect:
    """One detected defect from render_diagnose."""

    defect_type: DefectType
    start_s: float
    end_s: float
    severity: float = 1.0  # 0.0 = mild, 1.0 = severe
    rms_db: float = 0.0
    low_db: float = 0.0
    details: str = ""


@dataclass
class FixOperation:
    """One corrective operation in the ffmpeg filter chain."""

    start_s: float
    end_s: float
    ffmpeg_filter: str  # the filter string to apply
    description: str


@dataclass
class AutoFixPlan:
    """Complete auto-fix plan for a rendered mix."""

    defects: list[Defect] = field(default_factory=list)
    fixes: list[FixOperation] = field(default_factory=list)
    original_path: str = ""
    fixed_path: str = ""

    def generate_fixes(self) -> None:
        """Analyze defects and produce fix operations."""
        self.fixes = []
        for defect in self.defects:
            dur = defect.end_s - defect.start_s
            if dur <= 0:
                continue

            if defect.defect_type == DefectType.LEVEL_JUMP:
                # Smooth volume adjustment — compand doesn't support
                # enable='between(t,...)' so we use volume + afade instead.
                gain = 3.0 * defect.severity
                dur = max(0.1, defect.end_s - defect.start_s)
                self.fixes.append(
                    FixOperation(
                        start_s=defect.start_s,
                        end_s=defect.end_s,
                        ffmpeg_filter=f"volume={gain:.1f}dB",
                        description=f"Level jump fix at {defect.start_s:.1f}s "
                        f"({gain:.0f}dB adjust)",
                    )
                )

            elif defect.defect_type == DefectType.DROPOUT:
                gain_boost = 3.0 + 3.0 * defect.severity
                self.fixes.append(
                    FixOperation(
                        start_s=defect.start_s,
                        end_s=defect.end_s,
                        ffmpeg_filter=f"volume={gain_boost:.1f}dB",
                        description=f"Boost {gain_boost:.0f}dB at dropout {defect.start_s:.1f}s",
                    )
                )

            elif defect.defect_type == DefectType.BASS_THIN:
                boost_db = 3.0 + 3.0 * defect.severity
                self.fixes.append(
                    FixOperation(
                        start_s=defect.start_s,
                        end_s=defect.end_s,
                        ffmpeg_filter=(
                            f"equalizer=f=80:t=q:w=1.0:g={boost_db:.0f},"
                            f"equalizer=f=120:t=q:w=0.7:g={boost_db / 2:.0f}"
                        ),
                        description=f"Bass boost {boost_db:.0f}dB at {defect.start_s:.1f}s",
                    )
                )

            elif defect.defect_type == DefectType.ENTRY_SHOCK:
                fade_ms = int(200 + 300 * defect.severity)
                self.fixes.append(
                    FixOperation(
                        start_s=defect.start_s,
                        end_s=defect.start_s + fade_ms / 1000.0,
                        ffmpeg_filter=f"afade=t=in:d={fade_ms / 1000:.3f}",
                        description=f"Fade-in {fade_ms}ms at entry shock {defect.start_s:.1f}s",
                    )
                )

            elif defect.defect_type == DefectType.LOW_END_COLLAPSE:
                boost_db = 3.0 + 3.0 * defect.severity
                self.fixes.append(
                    FixOperation(
                        start_s=defect.start_s,
                        end_s=defect.end_s,
                        ffmpeg_filter=(
                            f"equalizer=f=80:t=q:w=1.0:g={boost_db:.0f},"
                            f"volume={boost_db * 0.5:.1f}dB"
                        ),
                        description=f"Low-end EQ+volume fix at {defect.start_s:.1f}s",
                    )
                )

            elif defect.defect_type == DefectType.PHASE_UNSTABLE:
                self.fixes.append(
                    FixOperation(
                        start_s=defect.start_s,
                        end_s=defect.end_s,
                        ffmpeg_filter="stereotools=mode=ms:level_in=1",
                        description=f"Mid-side processing for phase at {defect.start_s:.1f}s",
                    )
                )

    def ffmpeg_fix_chain(self, input_path: str, output_path: str) -> list[str]:
        """Generate complete ffmpeg argv with all fixes applied.

        Uses timeline editing (enable='between(t,start,end)') to apply
        each fix only during its time window, leaving the rest untouched.
        """
        self.generate_fixes()
        if not self.fixes:
            return ["cp", input_path, output_path]

        # Build compound filter with timeline enables
        filter_parts: list[str] = []
        for fix in self.fixes:
            enable = f"enable='between(t,{fix.start_s:.3f},{fix.end_s:.3f})'"
            filter_parts.extend(f"{part}:{enable}" for part in fix.ffmpeg_filter.split(","))

        compound = ",".join(filter_parts)
        return [
            "ffmpeg",
            "-i",
            input_path,
            "-af",
            compound,
            "-c:a",
            "libmp3lame",
            "-b:a",
            "320k",
            "-y",
            output_path,
        ]
