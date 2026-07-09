"""Firequalizer curve builders for per-track and master EQ."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.features import TrackFeatures

_MASTER_EQ_CURVE = [
    "entry(65, 0)",
    "entry(92, 0)",
    "entry(131, 0.5)",   # 60-130Hz sub weight
    "entry(185, 0.3)",
    "entry(262, -0.5)",   # 200-400Hz mud cut start
    "entry(370, -1.0)",   # 370Hz max cut
    "entry(523, -0.5)",
    "entry(740, 0)",
    "entry(1046, 0)",
    "entry(1480, 0)",
    "entry(2093, 0)",
    "entry(2960, 0)",
    "entry(4186, 0)",
    "entry(5920, 0.5)",   # 6-8kHz presence
    "entry(8372, 1.0)",   # 8-12kHz air start
    "entry(11840, 1.5)",  # 10-12kHz air peak
    "entry(16744, 1.2)",  # 16kHz gentle rolloff
    "entry(20000, 0.5)",  # 20kHz
]


def build_master_eq(
    mud_cut_db: float = -1.0, air_boost_db: float = 1.5, sub_boost_db: float = 0.5
) -> str:
    curve = []
    for entry in _MASTER_EQ_CURVE:
        parts = entry.strip("entry()").split(",")
        freq = float(parts[0].strip())
        gain = float(parts[1].strip())
        if 200 <= freq <= 500 and gain < 0:
            gain = mud_cut_db * (abs(gain) / 1.0)
        elif 6000 <= freq <= 20000 and gain > 0:
            gain = air_boost_db * (gain / 1.5)
        elif 60 <= freq <= 185 and gain > 0:
            gain = sub_boost_db * (gain / 0.5)
        curve.append(f"entry({int(freq)},{gain:.1f})")
    return ":".join(curve)


def build_per_track_eq(features: TrackFeatures) -> str:
    """Build per-track EQ curve from track audio features.

    Dark tracks (centroid < 2000 Hz): boost highs.
    Bright tracks (centroid > 3000 Hz): cut 2-4kHz.
    All tracks: gentle mid cut at 300-500Hz.
    """
    centroid = features.spectral_centroid_hz or 2200.0
    mid_cut = -1.0  # dB, configurable later

    entries = {
        "65": 0, "92": 0, "131": 0, "185": 0,
        "262": 0, "370": mid_cut / 2, "523": mid_cut,
        "740": mid_cut / 2, "1046": 0, "1480": 0,
    }

    if centroid > 3000:
        entries["2093"] = -0.5
        entries["2960"] = -1.0
        entries["4186"] = -0.5
        entries["5920"] = 0
        entries["8372"] = 0
        entries["11840"] = 0
    elif centroid < 2000:
        entries["2093"] = 0
        entries["2960"] = 0
        entries["4186"] = 0.5
        entries["5920"] = 0.8
        entries["8372"] = 1.2
        entries["11840"] = 1.5
    else:
        entries["2093"] = 0
        entries["2960"] = 0
        entries["4186"] = 0
        entries["5920"] = 0
        entries["8372"] = 0
        entries["11840"] = 0

    entries["16744"] = 0
    entries["20000"] = 0

    curve = [f"entry({freq},{gain:.1f})" for freq, gain in entries.items()]
    return f"firequalizer=gain_entry='{':'.join(curve)}'"


def build_preprocess_filter(ratio: float, gain_db: float, eq_filter: str) -> str:
    """Assemble per-track pre-processing filter chain."""
    return (
        f"highpass=f=30:t=4,"
        f"volume={gain_db:.2f}dB,"
        f"{eq_filter},"
        f"acompressor=threshold=-18dB:ratio=3:attack=10:release=80:"
        f"knee=6:detection=rms:link=average:makeup=1"
    )
