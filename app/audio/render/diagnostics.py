"""Post-render defect analysis + structural set flow analysis.

``scan_mix`` uses librosa (not ffmpeg) for audio loading.
``diagnose_mix`` uses librosa + scipy for 4s-window spectral analysis.
``analyze_set_flow`` combines per-track features with audio windows to
evaluate harmonic flow, BPM progression, energy arc and texture diversity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SR = 22050

# ── Camelot wheel reference (24-key, never changes) ──
_CAMELOT_WHEEL: list[dict[str, Any]] = [
    {"code": 0, "notation": "1A", "compat": {1, 2, 3, 4, 20, 22, 23}},
    {"code": 1, "notation": "1B", "compat": {0, 2, 3, 5, 21, 22, 23}},
    {"code": 2, "notation": "2A", "compat": {0, 1, 3, 4, 5, 6, 22}},
    {"code": 3, "notation": "2B", "compat": {0, 1, 2, 4, 5, 7, 23}},
    {"code": 4, "notation": "3A", "compat": {0, 2, 3, 5, 6, 7, 8}},
    {"code": 5, "notation": "3B", "compat": {1, 2, 3, 4, 6, 7, 9}},
    {"code": 6, "notation": "4A", "compat": {2, 4, 5, 7, 8, 9, 10}},
    {"code": 7, "notation": "4B", "compat": {3, 4, 5, 6, 8, 9, 11}},
    {"code": 8, "notation": "5A", "compat": {4, 6, 7, 9, 10, 11, 12}},
    {"code": 9, "notation": "5B", "compat": {5, 6, 7, 8, 10, 11, 13}},
    {"code": 10, "notation": "6A", "compat": {6, 8, 9, 11, 12, 13, 14}},
    {"code": 11, "notation": "6B", "compat": {7, 8, 9, 10, 12, 13, 15}},
    {"code": 12, "notation": "7A", "compat": {8, 10, 11, 13, 14, 15, 16}},
    {"code": 13, "notation": "7B", "compat": {9, 10, 11, 12, 14, 15, 17}},
    {"code": 14, "notation": "8A", "compat": {10, 12, 13, 15, 16, 17, 18}},
    {"code": 15, "notation": "8B", "compat": {11, 12, 13, 14, 16, 17, 19}},
    {"code": 16, "notation": "9A", "compat": {12, 14, 15, 17, 18, 19, 20}},
    {"code": 17, "notation": "9B", "compat": {13, 14, 15, 16, 18, 19, 21}},
    {"code": 18, "notation": "10A", "compat": {14, 16, 17, 19, 20, 21, 22}},
    {"code": 19, "notation": "10B", "compat": {15, 16, 17, 18, 20, 21, 23}},
    {"code": 20, "notation": "11A", "compat": {0, 16, 18, 19, 21, 22, 23}},
    {"code": 21, "notation": "11B", "compat": {1, 17, 18, 19, 20, 22, 23}},
    {"code": 22, "notation": "12A", "compat": {0, 1, 2, 18, 20, 21, 23}},
    {"code": 23, "notation": "12B", "compat": {0, 1, 3, 19, 20, 21, 22}},
]
_CAMELOT_COMPAT: dict[int, set[int]] = {e["code"]: e["compat"] for e in _CAMELOT_WHEEL}
_CAMELOT_NOTATION: dict[int, str] = {e["code"]: e["notation"] for e in _CAMELOT_WHEEL}


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
    stereo_corr: float | None = None
    stereo_width: float | None = None
    low_ratio: float | None = None
    centroid_hz: float | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DiagnoseReport:
    name: str
    duration_s: float
    overall_rms_db: float
    windows: list[DiagWindow] = field(default_factory=list)
    flagged: int = 0


def scan_mix(path: str) -> ScanReport:
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=8000, mono=True)
    y = y.astype(np.float32)
    win = int(sr)
    rms = np.array(
        [
            20 * np.log10(np.sqrt(np.mean(y[i : i + win] ** 2)) + 1e-9)
            for i in range(0, len(y) - win, win)
        ]
    )
    peak_db = float(20 * np.log10(np.max(np.abs(y)) + 1e-9))
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


def _camelot_distance(a: int, b: int) -> int:
    """Camelot wheel distance between two key codes (0-23).
    0 = same key, 1 = adjacent, 2 = two steps, >2 = incompatible.
    """
    if a == b:
        return 0
    compat = _CAMELOT_COMPAT.get(a, set())
    if b in compat:
        pos_a = a // 2
        pos_b = b // 2
        dist = min(abs(pos_a - pos_b), 12 - abs(pos_a - pos_b))
        return 1 if dist <= 1 else 2
    return 99


def _match_windows_to_segment(
    windows: list[DiagWindow], start_s: float, end_s: float
) -> tuple[float, float, float | None, float | None, float | None, list[str]]:
    """Aggregate DiagWindow metrics over a track segment time range."""
    import numpy as np

    selected = [w for w in windows if start_s <= w.offset_s < end_s]
    if not selected:
        return -60.0, -60.0, None, None, None, []

    rms_arr = np.array([w.rms_db for w in selected])
    low_arr = np.array([w.low_db for w in selected])
    centroids = [w.centroid_hz for w in selected if w.centroid_hz is not None]
    widths = [w.stereo_width for w in selected if w.stereo_width is not None]
    ratios = [w.low_ratio for w in selected if w.low_ratio is not None]
    all_tags = list(dict.fromkeys(t for w in selected for t in w.tags))
    return (
        float(np.mean(rms_arr)),
        float(np.mean(low_arr)),
        float(np.mean(centroids)) if centroids else None,
        float(np.mean(widths)) if widths else None,
        float(np.mean(ratios)) if ratios else None,
        all_tags,
    )


def analyze_set_flow(
    name: str,
    duration_s: float,
    windows: list[DiagWindow],
    segments: list[tuple[int, float, float]],
    features: dict[int, object],
    titles: dict[int, str],
    target_subgenre: str | None = None,
) -> dict[str, Any]:
    """Structural analysis of a DJ set combining audio windows and track features.

    Parameters
    ----------
    name : str
        Mix filename (e.g. "MIX.mp3").
    duration_s : float
        Total mix duration in seconds.
    windows : list[DiagWindow]
        Per-4s audio analysis from ``diagnose_mix``.
    segments : list[tuple[int, float, float]]
        Ordered track segments as ``(track_id, start_s, end_s)``.
    features : dict[int, object]
        Per-track feature objects (``TrackFeatures`` or dict) keyed by track_id.
    titles : dict[int, str]
        Human-readable track titles keyed by track_id.
    target_subgenre : str | None
        Optional subgenre tag for context-aware scoring.

    Returns
    -------
    dict
        JSON-serializable flow report with tracks, transitions, summary, warnings.
    """
    import numpy as np

    track_rows: list[dict[str, Any]] = []
    for idx, (tid, start_s, end_s) in enumerate(segments):
        feat = features.get(tid)
        bpm = getattr(feat, "bpm", None) if feat else None
        key_code = getattr(feat, "key_code", None) if feat else None
        lufs = getattr(feat, "integrated_lufs", None) if feat else None
        energy = getattr(feat, "energy_mean", None) if feat else None
        mood = getattr(feat, "mood", None) if feat else None

        seg_rms, seg_low, seg_cent, seg_width, seg_lowr, seg_tags = _match_windows_to_segment(
            windows, start_s, end_s
        )

        track_rows.append(
            {
                "track_id": tid,
                "sequence_index": idx,
                "title": titles.get(tid, f"Track {tid}"),
                "start_s": round(start_s, 1),
                "end_s": round(end_s, 1),
                "bpm": bpm,
                "key_code": key_code,
                "key_notation": _CAMELOT_NOTATION.get(key_code) if key_code is not None else None,
                "integrated_lufs": lufs,
                "energy": energy,
                "mood": mood,
                "segment_rms_db": round(seg_rms, 1),
                "segment_low_db": round(seg_low, 1),
                "segment_centroid_hz": round(seg_cent, 0) if seg_cent is not None else None,
                "segment_stereo_width": round(seg_width, 3) if seg_width is not None else None,
                "segment_low_ratio": round(seg_lowr, 4) if seg_lowr is not None else None,
                "segment_flags": seg_tags,
            }
        )

    transitions: list[dict[str, Any]] = []
    for i in range(len(track_rows) - 1):
        a, b = track_rows[i], track_rows[i + 1]
        kc_a, kc_b = a["key_code"], b["key_code"]
        camelot_compat: bool | None = None
        camelot_dist: int | None = None
        if kc_a is not None and kc_b is not None:
            camelot_dist = _camelot_distance(kc_a, kc_b)
            camelot_compat = camelot_dist <= 2

        bpm_delta = 0.0
        if a["bpm"] is not None and b["bpm"] is not None:
            bpm_delta = round(b["bpm"] - a["bpm"], 1)

        energy_delta: float | None = None
        if a["energy"] is not None and b["energy"] is not None:
            energy_delta = round(b["energy"] - a["energy"], 3)

        transitions.append(
            {
                "from_index": i,
                "to_index": i + 1,
                "from_track_id": a["track_id"],
                "to_track_id": b["track_id"],
                "from_title": a["title"],
                "to_title": b["title"],
                "from_key_notation": a["key_notation"],
                "to_key_notation": b["key_notation"],
                "camelot_compatible": camelot_compat,
                "camelot_distance": camelot_dist,
                "bpm_delta": bpm_delta,
                "energy_delta": energy_delta,
            }
        )

    n_trans = len(transitions)
    camelot_compat_count = sum(1 for t in transitions if t["camelot_compatible"] is True)
    camelot_conflicts = sum(1 for t in transitions if t["camelot_compatible"] is False)
    camelot_unknown = sum(1 for t in transitions if t["camelot_compatible"] is None)

    bpm_deltas = [abs(t["bpm_delta"]) for t in transitions]
    max_bpm_jump = max(bpm_deltas) if bpm_deltas else 0.0
    avg_abs_bpm_jump = round(sum(bpm_deltas) / len(bpm_deltas), 2) if bpm_deltas else 0.0

    energies = [t["energy"] for t in track_rows if t["energy"] is not None]
    energy_std = round(float(np.std(energies)), 3) if len(energies) > 1 else None

    centroids = [
        t["segment_centroid_hz"] for t in track_rows if t["segment_centroid_hz"] is not None
    ]
    centroid_std = round(float(np.std(centroids)), 0) if len(centroids) > 1 else None

    low_ratios = [t["segment_low_ratio"] for t in track_rows if t["segment_low_ratio"] is not None]
    low_ratio_std = round(float(np.std(low_ratios)), 4) if len(low_ratios) > 1 else None

    rms_values = [t["segment_rms_db"] for t in track_rows]
    rms_std = round(float(np.std(rms_values)), 1) if len(rms_values) > 1 else None

    quality_components: list[float] = []
    if n_trans and camelot_compat_count + camelot_conflicts > 0:
        total = camelot_compat_count + camelot_conflicts
        camelot_score = 1.0 - (camelot_conflicts / total)
        quality_components.append(camelot_score * 0.30)
    if bpm_deltas:
        bpm_smoothness = max(0.0, 1.0 - (avg_abs_bpm_jump / 8.0))
        quality_components.append(bpm_smoothness * 0.25)
    if energy_std is not None:
        eq = (
            1.0
            if energy_std < 0.1
            else (0.8 if energy_std < 0.2 else (0.5 if energy_std < 0.3 else 0.2))
        )
        quality_components.append(eq * 0.25)
    if centroid_std is not None:
        tq = (
            0.3
            if centroid_std < 100
            else (0.7 if centroid_std < 300 else (0.9 if centroid_std < 600 else 0.5))
        )
        quality_components.append(tq * 0.20)
    quality_score = (
        round(sum(quality_components) / len(quality_components), 3) if quality_components else 0.0
    )

    warnings: list[str] = []
    for t in transitions:
        if t["camelot_compatible"] is False:
            warnings.append(
                f"Transition {t['from_title']} \u2192 {t['to_title']}: "
                f"Camelot conflict {t['from_key_notation']} \u2192 {t['to_key_notation']}"
            )
        elif t["camelot_compatible"] is None:
            warnings.append(f"Transition {t['from_title']} \u2192 {t['to_title']}: key unknown")
        if abs(t["bpm_delta"]) > 5:
            warnings.append(
                f"Transition {t['from_title']} \u2192 {t['to_title']}: "
                f"large BPM jump {t['bpm_delta']:+.1f}"
            )
    if energy_std is not None and energy_std < 0.02 and len(energies) > 1:
        warnings.append("Energy arc is very flat \u2014 consider more dynamic track selection")
    if centroid_std is not None and centroid_std < 80 and len(centroids) > 1:
        warnings.append("Spectral texture is very uniform \u2014 risk of listener fatigue")

    return {
        "name": name,
        "duration_s": round(duration_s, 1),
        "num_tracks": len(track_rows),
        "target_subgenre": target_subgenre,
        "tracks": track_rows,
        "transitions": transitions,
        "summary": {
            "camelot_compatible": camelot_compat_count,
            "camelot_conflicts": camelot_conflicts,
            "camelot_unknown": camelot_unknown,
            "camelot_total": n_trans,
            "max_bpm_jump": max_bpm_jump,
            "avg_abs_bpm_jump": avg_abs_bpm_jump,
            "energy_std": energy_std,
            "centroid_std": centroid_std,
            "low_ratio_std": low_ratio_std,
            "rms_std": rms_std,
            "quality_score": quality_score,
        },
        "warnings": warnings,
    }


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
        y_st, _ = librosa.load(path, sr=sr, offset=off, duration=win, mono=False)
        if y_st.ndim == 1:
            left = right = y_st
            mono = y_st
        else:
            left = y_st[0]
            right = y_st[1]
            mono = (left + right) / 2.0
        rms = 20 * np.log10(np.sqrt(np.mean(mono**2)) + 1e-9)
        low = sosfiltfilt(losos, mono).astype(np.float32)
        lo_rms = 20 * np.log10(np.sqrt(np.mean(low**2)) + 1e-9)
        if np.std(left) > 1e-9 and np.std(right) > 1e-9:
            corr = float(np.corrcoef(left, right)[0, 1])
        else:
            corr = 1.0
        width = float(np.std(left - right) / (np.std(left + right) + 1e-9))
        spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
        freqs = np.fft.rfftfreq(len(mono), 1 / sr)
        total = float(np.sum(spec) + 1e-12)
        low_ratio = float(np.sum(spec[(freqs >= 20) & (freqs < 120)])) / total
        centroid = float(np.sum(freqs * spec) / total)
        rows.append((off, float(rms), float(lo_rms), corr, width, low_ratio, centroid))

    rms_arr = np.array([r[1] for r in rows]) if rows else np.array([0.0])
    mean = float(rms_arr.mean())
    windows: list[DiagWindow] = []
    flagged = 0
    for i, (off, r, lo, corr, width, low_ratio, centroid) in enumerate(rows):
        tags: list[str] = []
        if i > 0 and abs(r - rows[i - 1][1]) > 5:
            tags.append(f"LEVEL-JUMP {r - rows[i - 1][1]:+.0f}dB")
        if r < mean - 7:
            tags.append(f"DROPOUT {r:.0f}dB")
        if lo < r - 22:
            tags.append("bass-thin")
        if corr < 0.2 or width > 0.9:
            tags.append("PHASE-UNSTABLE")
        if i > 0:
            prev_r = rows[i - 1][1]
            prev_low_ratio = rows[i - 1][5]
            prev_centroid = rows[i - 1][6]
            if (r - prev_r) > 10 or (
                (r - prev_r) > 5 and r > -14 and centroid > max(1800.0, prev_centroid * 1.05)
            ):
                tags.append("ENTRY-SHOCK")
            if prev_low_ratio > 0 and low_ratio < prev_low_ratio * 0.25 and (r - prev_r) > 3:
                tags.append("LOW-END-COLLAPSE")
        if tags:
            flagged += 1
        windows.append(
            DiagWindow(
                offset_s=off,
                rms_db=r,
                low_db=lo,
                stereo_corr=corr,
                stereo_width=width,
                low_ratio=low_ratio,
                centroid_hz=centroid,
                tags=tags,
            )
        )
    return DiagnoseReport(
        name=Path(path).name, duration_s=dur, overall_rms_db=mean, windows=windows, flagged=flagged
    )
