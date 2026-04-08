"""Domain constants, enums, and static reference data.

Non-configurable values that define the system's vocabulary.
For tunable values, see app/config.py.
"""

from enum import IntEnum, StrEnum


class TrackStatus(IntEnum):
    ACTIVE = 0
    ARCHIVED = 1


class SectionType(IntEnum):
    """Track structure section types (REQUIREMENTS §10.2: 0-11)."""

    INTRO = 0
    ATTACK = 1
    BUILD = 2
    PRE_DROP = 3
    DROP = 4
    PEAK = 5
    BREAKDOWN = 6
    OUTRO = 7
    RISE = 8
    VALLEY = 9
    SUSTAIN = 10
    AMBIENT = 11


class CueKind(IntEnum):
    """Cue point types (REQUIREMENTS §10.2: 0-7)."""

    CUE = 0
    HOT_CUE_1 = 1
    HOT_CUE_2 = 2
    HOT_CUE_3 = 3
    HOT_CUE_4 = 4
    HOT_CUE_5 = 5
    HOT_CUE_6 = 6
    HOT_CUE_7 = 7


class TechnoSubgenre(StrEnum):
    """15 subgenres ordered by energy intensity (low -> high)."""

    AMBIENT_DUB = "ambient_dub"
    DUB_TECHNO = "dub_techno"
    MINIMAL = "minimal"
    DETROIT = "detroit"
    MELODIC_DEEP = "melodic_deep"
    PROGRESSIVE = "progressive"
    HYPNOTIC = "hypnotic"
    DRIVING = "driving"
    TRIBAL = "tribal"
    BREAKBEAT = "breakbeat"
    PEAK_TIME = "peak_time"
    ACID = "acid"
    RAW = "raw"
    INDUSTRIAL = "industrial"
    HARD_TECHNO = "hard_techno"


class ExportFormat(StrEnum):
    M3U8 = "m3u8"
    REKORDBOX_XML = "rekordbox_xml"
    JSON_GUIDE = "json_guide"
    CHEAT_SHEET = "cheat_sheet"


class TargetApp(StrEnum):
    TRAKTOR = "traktor"
    REKORDBOX = "rekordbox"
    DJAY = "djay"
    GENERIC = "generic"


class Provider(StrEnum):
    YANDEX_MUSIC = "yandex_music"
    SPOTIFY = "spotify"
    BEATPORT = "beatport"
    SOUNDCLOUD = "soundcloud"


class SetTemplate(StrEnum):
    WARM_UP_30 = "warm_up_30"
    CLASSIC_60 = "classic_60"
    PEAK_HOUR_60 = "peak_hour_60"
    ROLLER_90 = "roller_90"
    PROGRESSIVE_120 = "progressive_120"
    WAVE_120 = "wave_120"
    CLOSING_60 = "closing_60"
    FULL_LIBRARY = "full_library"


class TransitionStyle(StrEnum):
    """Recommended *type* of transition for an A→B pair.

    Picked by ``TransitionScorer.recommend_style()`` from the 6-component
    score plus the hard-reject status. The DJ engine consumes this to
    choose its mix length and automation pattern (length in bars, EQ
    automation, optional FX). Style only encodes *how* to play the
    transition — *whether* to play it at all is decided by the score
    upstream.

    Ordered roughly from most-confident-blend to last-resort.
    """

    # Bars / behaviour are advisory; the engine maps each style to its
    # own parameters in TRANSITION_STYLE_PROFILES below.
    CUT = "cut"
    """Hard cut on the bar — perfect BPM/key/groove match, no overlap needed."""

    BASS_SWAP_SHORT = "bass_swap_short"
    """8-bar bass-swap blend — good match, just enough overlap to swap kicks."""

    BASS_SWAP_LONG = "bass_swap_long"
    """32-bar bass-swap blend — DJ default, room for breathing and EQ work."""

    LONG_BLEND = "long_blend"
    """64-bar tonal blend — slow harmonic shift, useful when energy matches but key drifts."""

    ECHO_OUT = "echo_out"
    """Outgoing track tail-stops with an echo/reverb hold — for big energy gaps."""

    FILTER_SWEEP = "filter_sweep"
    """Outgoing HPF-swept upward to free spectrum — last resort for collisions."""


# Per-style mix length (bars) + a short reason. The engine looks these
# up by style; tests assert the table covers every style. Bars stay in
# DJ-native units so the audio engine can still convert them via the
# active deck's BPM at runtime.
TRANSITION_STYLE_PROFILES: dict[TransitionStyle, dict[str, float | str]] = {
    TransitionStyle.CUT: {"bars": 0, "reason": "perfect match — drop on the bar"},
    TransitionStyle.BASS_SWAP_SHORT: {"bars": 8, "reason": "good match — quick bass swap"},
    TransitionStyle.BASS_SWAP_LONG: {
        "bars": 32,
        "reason": "default blend — bass swap with breathing room",
    },
    TransitionStyle.LONG_BLEND: {"bars": 64, "reason": "key shift — slow harmonic blend"},
    TransitionStyle.ECHO_OUT: {"bars": 16, "reason": "energy gap — tail outgoing with echo"},
    TransitionStyle.FILTER_SWEEP: {"bars": 16, "reason": "spectral collision — HPF the outgoing"},
}


# Camelot wheel: 24 keys, static reference data
# key_code -> (camelot_notation, key_name)
CAMELOT_KEYS: dict[int, tuple[str, str]] = {
    0: ("1A", "A\u266d minor"),
    1: ("1B", "B major"),
    2: ("2A", "E\u266d minor"),
    3: ("2B", "F\u266f major"),
    4: ("3A", "B\u266d minor"),
    5: ("3B", "D\u266d major"),
    6: ("4A", "F minor"),
    7: ("4B", "A\u266d major"),
    8: ("5A", "C minor"),
    9: ("5B", "E\u266d major"),
    10: ("6A", "G minor"),
    11: ("6B", "B\u266d major"),
    12: ("7A", "D minor"),
    13: ("7B", "F major"),
    14: ("8A", "A minor"),
    15: ("8B", "C major"),
    16: ("9A", "E minor"),
    17: ("9B", "G major"),
    18: ("10A", "B minor"),
    19: ("10B", "D major"),
    20: ("11A", "F\u266f minor"),
    21: ("11B", "A major"),
    22: ("12A", "D\u266d minor"),
    23: ("12B", "E major"),
}

# Domain constraint ranges
BPM_MIN: float = 20.0
BPM_MAX: float = 300.0

CONFIDENCE_MIN: float = 0.0
CONFIDENCE_MAX: float = 1.0

ENERGY_MIN: float = 0.0
ENERGY_MAX: float = 1.0

HOTCUE_INDEX_MIN: int = 0
HOTCUE_INDEX_MAX: int = 15

KEY_CODE_MIN: int = 0
KEY_CODE_MAX: int = 23

# Transition scoring weights (default, overridable per-template)
DEFAULT_TRANSITION_WEIGHTS: dict[str, float] = {
    "bpm": 0.22,
    "harmonic": 0.20,
    "energy": 0.23,
    "spectral": 0.15,
    "groove": 0.10,
    "timbral": 0.10,
}
