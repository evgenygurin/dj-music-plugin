"""Post-render defect analysis (ported from scan() + diagnose())."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_SR = 22050


@dataclass(frozen=True, slots=True)
class ScanReport:
    name: str
    duration_s: float
    true_peak_db: float
    clip_risk: bool
    level_jumps: list[tuple[int, float]] = field(default_factory=list)
    near_silent_s: list[int] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DiagWindow:
    offset_s: float
    rms_db: float
    low_db: float
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DiagnoseReport:
    name: str
    duration_s: float
    overall_rms_db: float
    windows: list[DiagWindow] = field(default_factory=list)
    flagged: int = 0


def scan_mix(path: str) -> ScanReport:
    import numpy as np

    tmp = "/tmp/_scan.f32"
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "8000", "-f", "f32le", tmp],
        stderr=subprocess.DEVNULL,
        check=False,
    )
    y = np.fromfile(tmp, dtype="<f4")
    sr = 8000
    win = sr
    rms = np.array(
        [
            20 * np.log10(np.sqrt(np.mean(y[i : i + win] ** 2)) + 1e-9)
            for i in range(0, len(y) - win, win)
        ]
    )
    vd = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    ).stderr
    peak_db = 0.0
    for line in vd.splitlines():
        if "max_volume" in line:
            peak_db = float(line.split("max_volume:")[1].split("dB")[0])
    jumps = [
        (i, float(rms[i + 1] - rms[i]))
        for i in range(len(rms) - 1)
        if abs(rms[i + 1] - rms[i]) > 6.0
    ]
    sil = [i for i in range(len(rms)) if rms[i] < -45]
    return ScanReport(
        name=Path(path).name,
        duration_s=len(y) / sr,
        true_peak_db=peak_db,
        clip_risk=peak_db >= -0.1,
        level_jumps=jumps,
        near_silent_s=sil,
    )


def diagnose_mix(path: str) -> DiagnoseReport:
    import librosa
    import numpy as np
    from scipy.signal import butter, sosfiltfilt

    win, sr = 4.0, _SR
    losos = butter(4, 150, btype="low", fs=sr, output="sos")
    dur = librosa.get_duration(path=path)
    rows = []
    for i in range(int((dur - win) // win)):
        off = i * win
        y, _ = librosa.load(path, sr=sr, offset=off, duration=win, mono=True)
        rms = 20 * np.log10(np.sqrt(np.mean(y**2)) + 1e-9)
        low = sosfiltfilt(losos, y).astype(np.float32)
        lo_rms = 20 * np.log10(np.sqrt(np.mean(low**2)) + 1e-9)
        rows.append((off, float(rms), float(lo_rms)))

    rms_arr = np.array([r[1] for r in rows]) if rows else np.array([0.0])
    mean = float(rms_arr.mean())
    windows: list[DiagWindow] = []
    flagged = 0
    for i, (off, r, lo) in enumerate(rows):
        tags: list[str] = []
        if i > 0 and abs(r - rows[i - 1][1]) > 5:
            tags.append(f"LEVEL-JUMP {r - rows[i - 1][1]:+.0f}dB")
        if r < mean - 7:
            tags.append(f"DROPOUT {r:.0f}dB")
        if lo < r - 22:
            tags.append("bass-thin")
        if tags:
            flagged += 1
        windows.append(DiagWindow(offset_s=off, rms_db=r, low_db=lo, tags=tags))
    return DiagnoseReport(
        name=Path(path).name, duration_s=dur, overall_rms_db=mean, windows=windows, flagged=flagged
    )
