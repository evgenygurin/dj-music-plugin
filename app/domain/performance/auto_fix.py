"""AutoFixRender — automatic repair of render diagnostics defects.

After render_diagnose finds defects (level jumps, dropouts, bass-thin,
phase issues, entry shocks, low-end collapse), this module generates
corrective ffmpeg filter graphs to fix them automatically.

Fix strategies:
  LEVEL-JUMP: apply downward compression at the jump point
  DROPOUT: apply makeup gain (+3-6 dB) at the dropout
  BASS-THIN: boost sub-bass (60-120 Hz) during affected window
  PHASE-UNSTABLE: apply mid-side processing to widen stereo safely
  ENTRY-SHOCK: apply short fade-in (100-500 ms)
  LOW-END-COLLAPSE: apply multiband compression on low band
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
                # Apply compression: threshold = current level - 3dB, ratio 4:1
                threshold = defect.rms_db - 3.0
                self.fixes.append(FixOperation(
                    start_s=defect.start_s, end_s=defect.end_s,
                    ffmpeg_filter=(
                        f"compand=attacks=0.001:decays=0.1:"
                        f"points=-80/-80|{threshold}/{threshold}|"
                        f"0/-{6 * defect.severity}|20/-{12 * defect.severity}:"
                        f"gain=0:volume=-90"
                    ),
                    description=f"Compress level jump at {defect.start_s:.1f}s "
                                f"(threshold={threshold:.0f}dB, severity={defect.severity:.1f})",
                ))

            elif defect.defect_type == DefectType.DROPOUT:
                gain_boost = 3.0 + 3.0 * defect.severity
                self.fixes.append(FixOperation(
                    start_s=defect.start_s, end_s=defect.end_s,
                    ffmpeg_filter=f"volume={gain_boost:.1f}dB",
                    description=f"Boost {gain_boost:.0f}dB at dropout {defect.start_s:.1f}s",
                ))

            elif defect.defect_type == DefectType.BASS_THIN:
                boost_db = 3.0 + 3.0 * defect.severity
                self.fixes.append(FixOperation(
                    start_s=defect.start_s, end_s=defect.end_s,
                    ffmpeg_filter=(
                        f"equalizer=f=80:t=q:w=1.0:g={boost_db:.0f},"
                        f"equalizer=f=120:t=q:w=0.7:g={boost_db/2:.0f}"
                    ),
                    description=f"Bass boost {boost_db:.0f}dB at {defect.start_s:.1f}s",
                ))

            elif defect.defect_type == DefectType.ENTRY_SHOCK:
                fade_ms = int(200 + 300 * defect.severity)
                self.fixes.append(FixOperation(
                    start_s=defect.start_s, end_s=defect.start_s + fade_ms / 1000.0,
                    ffmpeg_filter=f"afade=t=in:d={fade_ms/1000:.3f}",
                    description=f"Fade-in {fade_ms}ms at entry shock {defect.start_s:.1f}s",
                ))

            elif defect.defect_type == DefectType.LOW_END_COLLAPSE:
                self.fixes.append(FixOperation(
                    start_s=defect.start_s, end_s=defect.end_s,
                    ffmpeg_filter=(
                        "mcompand=args='0.005 0.1 -40/-40 0/0 6'"
                    ),
                    description=f"Multiband comp on low end at {defect.start_s:.1f}s",
                ))

            elif defect.defect_type == DefectType.PHASE_UNSTABLE:
                self.fixes.append(FixOperation(
                    start_s=defect.start_s, end_s=defect.end_s,
                    ffmpeg_filter="stereotools=mode=ms:level_in=1",
                    description=f"Mid-side processing for phase at {defect.start_s:.1f}s",
                ))

    def ffmpeg_fix_chain(self, input_path: str, output_path: str) -> str:
        """Generate complete ffmpeg command with all fixes applied.

        Uses timeline editing (enable='between(t,start,end)') to apply
        each fix only during its time window, leaving the rest untouched.
        """
        self.generate_fixes()
        if not self.fixes:
            return f"cp '{input_path}' '{output_path}'  # no fixes needed"

        # Build compound filter with timeline enables
        filter_parts = []
        for fix in self.fixes:
            enable = f"enable='between(t,{fix.start_s:.3f},{fix.end_s:.3f})'"
            filter_parts.append(f"{fix.ffmpeg_filter}:{enable}")

        compound = ",".join(filter_parts)
        return (
            f"ffmpeg -i '{input_path}' -af '{compound}' "
            f"-c:a libmp3lame -b:a 320k -y '{output_path}'"
        )
