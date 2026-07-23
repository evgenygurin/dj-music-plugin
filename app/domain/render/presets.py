"""Named DSP preset profiles for each techno subgenre.

Each preset is a ``RenderRequestOverrides``-compatible dict (partial).
All values are optional — only the fields that differ from ``RenderSettings`` defaults.

Research sources (July 2026):
- TrackScore.ai Techno Mixing Guide — DR/LUFS targets per subgenre
- MixMasterAI Techno Mastering Guide — EQ profiles, compression, LUFS
- Mixgraph Techno Mixing Guide — spectral balance per subgenre
- Attack Magazine, Gearspace, Grokipedia — genre-specific production techniques
- CueArtists.eu — club system translation guide
"""

from __future__ import annotations

from typing import Any

# ──────────────────────────────────────────────
# Hypnotic Techno
# ──────────────────────────────────────────────
# Deep, repetitive, atmospheric. Minimalism through subtraction.
# Long evolving textures, sub-bass focus, rolled-off highs.
# DR: 8-12 dB, LUFS: -8 to -10, BPM: 120-135
HYPNOTIC: dict[str, Any] = {
    # ── Low-end ──
    "hpf_cutoff_hz": 25.0,  # Let deep sub through (20-60Hz is hypnotic territory)
    # ── Per-track EQ: gentle, warm ──
    "per_track_eq_mid_cut_db": -0.5,  # Minimal — warmth is the point
    "per_track_eq_bright_boost_db": 0.5,  # Very gentle air, never harsh
    # ── Pre-compressor: light ──
    "pre_comp_threshold_db": -16.0,
    "pre_comp_ratio": 2.5,
    "pre_comp_attack_ms": 15.0,
    "pre_comp_release_ms": 100.0,
    # ── Glue compressor: very gentle ──
    "glue_comp_threshold_db": -12.0,
    "glue_comp_ratio": 2.0,
    "glue_comp_attack_ms": 40.0,
    "glue_comp_release_ms": 200.0,
    # ── Master EQ: warm sub, dark top ──
    "master_eq_air_boost_db": 1.0,  # Subtle air
    "master_eq_mud_cut_db": -0.5,  # Gentle — warmth preferred
    "master_eq_sub_boost_db": 1.0,  # Deep sub presence
    # ── Limiter: preserve dynamics ──
    "limiter_attack_ms": 15.0,  # Slower = punch preserved
    "limiter_release_ms": 40.0,
    "limiter_ceiling": 0.88,  # -1.2 dBFS headroom
    # ── Normalisation: subtle ──
    "dynaudnorm_maxgain": 1.5,
    # ── Crossover geometry: wider midrange ──
    "xsplit_low_hz": 200,
    "xsplit_high_hz": 4500,
    # ── Transition timing: slow, evolving ──
    "eq_phase_1_ratio": 0.35,
    "eq_phase_2_ratio": 0.65,
    "low_swap_beats": 2.0,  # Long bass crossfade = smooth evolution
    "outro_fade_bars": 16,  # Long fade
}

# ──────────────────────────────────────────────
# Industrial Techno
# ──────────────────────────────────────────────
# Aggressive, distorted, raw, mechanical.
# Heavy compression, mid-range aggression, noise textures.
# DR: 5-7 dB, LUFS: -6 to -7, BPM: 140-155+
INDUSTRIAL: dict[str, Any] = {
    "hpf_cutoff_hz": 30.0,
    # ── Per-track EQ: aggressive clarity ──
    "per_track_eq_mid_cut_db": -1.5,  # Aggressive mud cut for clarity
    "per_track_eq_bright_boost_db": 2.0,  # Aggressive highs for metallic bite
    # ── Pre-compressor: heavy, fast ──
    "pre_comp_threshold_db": -20.0,
    "pre_comp_ratio": 4.0,
    "pre_comp_attack_ms": 8.0,
    "pre_comp_release_ms": 60.0,
    # ── Glue compressor: heavy pumping ──
    "glue_comp_threshold_db": -16.0,
    "glue_comp_ratio": 4.0,
    "glue_comp_attack_ms": 20.0,
    "glue_comp_release_ms": 120.0,
    # ── Master EQ: bright, aggressive ──
    "master_eq_air_boost_db": 2.0,
    "master_eq_mud_cut_db": -1.5,
    "master_eq_sub_boost_db": 0.3,  # Less sub — the distortion IS the bass
    # ── Limiter: aggressive ──
    "limiter_attack_ms": 5.0,
    "limiter_release_ms": 20.0,
    "limiter_ceiling": 0.80,
    # ── Normalisation: push hard ──
    "dynaudnorm_maxgain": 3.0,
    # ── Crossover: standard ──
    "xsplit_low_hz": 250,
    "xsplit_high_hz": 4000,
    # ── Transition timing: fast, abrupt ──
    "eq_phase_1_ratio": 0.30,
    "eq_phase_2_ratio": 0.60,
    "low_swap_beats": 0.5,  # Fast bass swap = mechanical feel
    "outro_fade_bars": 8,
}

# ──────────────────────────────────────────────
# Hard Techno
# ──────────────────────────────────────────────
# Punishing kicks, maximum punch, relentless drive.
# Extreme compression, bright top-end, minimal dynamic range.
# DR: 4-6 dB, LUFS: -5 to -7, BPM: 150-160+
HARD: dict[str, Any] = {
    "hpf_cutoff_hz": 35.0,  # Tighter low-end for maximum punch
    # ── Per-track EQ: very aggressive ──
    "per_track_eq_mid_cut_db": -2.0,  # Maximum mud removal
    "per_track_eq_bright_boost_db": 2.5,  # Piercing highs
    # ── Pre-compressor: extreme ──
    "pre_comp_threshold_db": -22.0,
    "pre_comp_ratio": 6.0,
    "pre_comp_attack_ms": 5.0,
    "pre_comp_release_ms": 40.0,
    # ── Glue compressor: extreme ──
    "glue_comp_threshold_db": -18.0,
    "glue_comp_ratio": 5.0,
    "glue_comp_attack_ms": 15.0,
    "glue_comp_release_ms": 80.0,
    # ── Master EQ: bright, aggressive ──
    "master_eq_air_boost_db": 2.5,
    "master_eq_mud_cut_db": -2.0,
    "master_eq_sub_boost_db": 0.2,  # Kick IS the bass
    # ── Limiter: brickwall ──
    "limiter_attack_ms": 3.0,
    "limiter_release_ms": 15.0,
    "limiter_ceiling": 0.75,  # Maximum loudness
    # ── Normalisation: push to max ──
    "dynaudnorm_maxgain": 4.0,
    # ── Crossover: tight lows ──
    "xsplit_low_hz": 300,
    "xsplit_high_hz": 5000,
    # ── Transition timing: lightning fast ──
    "eq_phase_1_ratio": 0.25,
    "eq_phase_2_ratio": 0.55,
    "low_swap_beats": 0.5,  # Instant bass swap
    "outro_fade_bars": 4,  # Abrupt
}

# ──────────────────────────────────────────────
# Dub Techno
# ──────────────────────────────────────────────
# Warm, spacious, deep. Heavy reverb/delay, minimal compression.
# Inspired by Basic Channel / Chain Reaction aesthetic.
# DR: 8-12 dB, LUFS: -8 to -10, BPM: 120-130
DUB: dict[str, Any] = {
    "hpf_cutoff_hz": 20.0,  # Maximum sub — dub lives at 30-50Hz
    # ── Per-track EQ: warm, minimal ──
    "per_track_eq_mid_cut_db": -0.3,  # Almost none — preserve analog warmth
    "per_track_eq_bright_boost_db": 0.0,  # Rolled-off highs — the dub darkness
    # ── Pre-compressor: very light ──
    "pre_comp_threshold_db": -14.0,
    "pre_comp_ratio": 2.0,
    "pre_comp_attack_ms": 20.0,
    "pre_comp_release_ms": 150.0,
    # ── Glue compressor: extremely gentle ──
    "glue_comp_threshold_db": -10.0,
    "glue_comp_ratio": 1.5,
    "glue_comp_attack_ms": 50.0,
    "glue_comp_release_ms": 250.0,
    # ── Master EQ: warm sub, no air ──
    "master_eq_air_boost_db": 0.0,  # No artificial brightness
    "master_eq_mud_cut_db": -0.3,  # Barely touch
    "master_eq_sub_boost_db": 2.0,  # Heavy sub — the dub weight
    # ── Limiter: maximum headroom ──
    "limiter_attack_ms": 20.0,
    "limiter_release_ms": 50.0,
    "limiter_ceiling": 0.90,  # -0.9 dBFS — let dynamics breathe
    # ── Normalisation: minimal ──
    "dynaudnorm_maxgain": 0.5,
    # ── Crossover: very wide ──
    "xsplit_low_hz": 180,
    "xsplit_high_hz": 3500,
    # ── Transition timing: glacial, psychedelic ──
    "eq_phase_1_ratio": 0.45,
    "eq_phase_2_ratio": 0.75,
    "low_swap_beats": 4.0,  # Very slow bass crossfade
    "outro_fade_bars": 24,  # Extremely long fade
}

# ──────────────────────────────────────────────
# Peak-Time Techno
# ──────────────────────────────────────────────
# Big room, anthemic, relentless. Maximum energy with clarity.
# Open sound, boosted air, heavy sub presence.
# DR: 6-8 dB, LUFS: -6 to -8, BPM: 128-145
PEAK_TIME: dict[str, Any] = {
    "hpf_cutoff_hz": 30.0,
    # ── Per-track EQ: open, present ──
    "per_track_eq_mid_cut_db": -1.0,  # Moderate — clarity matters
    "per_track_eq_bright_boost_db": 2.0,  # Lots of air for big-room feel
    # ── Pre-compressor: moderate ──
    "pre_comp_threshold_db": -18.0,
    "pre_comp_ratio": 3.0,
    "pre_comp_attack_ms": 10.0,
    "pre_comp_release_ms": 80.0,
    # ── Glue compressor: moderate ──
    "glue_comp_threshold_db": -14.0,
    "glue_comp_ratio": 3.0,
    "glue_comp_attack_ms": 30.0,
    "glue_comp_release_ms": 150.0,
    # ── Master EQ: open, energetic ──
    "master_eq_air_boost_db": 2.0,
    "master_eq_mud_cut_db": -1.0,
    "master_eq_sub_boost_db": 1.0,
    # ── Limiter: moderate-aggressive ──
    "limiter_attack_ms": 8.0,
    "limiter_release_ms": 25.0,
    "limiter_ceiling": 0.82,
    # ── Normalisation: standard ──
    "dynaudnorm_maxgain": 2.0,
    # ── Crossover: standard ──
    "xsplit_low_hz": 250,
    "xsplit_high_hz": 4000,
    # ── Transition timing: driving ──
    "eq_phase_1_ratio": 0.35,
    "eq_phase_2_ratio": 0.65,
    "low_swap_beats": 1.0,
    "outro_fade_bars": 12,
}

# ──────────────────────────────────────────────
# Driving Techno
# ──────────────────────────────────────────────
# Forward momentum, rolling energy, steady groove.
# Balanced mix, clear mids for drive, functional.
# DR: 6-8 dB, LUFS: -7 to -8, BPM: 128-140
DRIVING: dict[str, Any] = {
    "hpf_cutoff_hz": 30.0,
    # ── Per-track EQ: moderate, clear ──
    "per_track_eq_mid_cut_db": -0.8,
    "per_track_eq_bright_boost_db": 1.5,
    # ── Pre-compressor: moderate ──
    "pre_comp_threshold_db": -17.0,
    "pre_comp_ratio": 2.8,
    "pre_comp_attack_ms": 12.0,
    "pre_comp_release_ms": 90.0,
    # ── Glue compressor: moderate ──
    "glue_comp_threshold_db": -13.0,
    "glue_comp_ratio": 2.5,
    "glue_comp_attack_ms": 35.0,
    "glue_comp_release_ms": 180.0,
    # ── Master EQ: balanced ──
    "master_eq_air_boost_db": 1.5,
    "master_eq_mud_cut_db": -0.8,
    "master_eq_sub_boost_db": 0.8,
    # ── Limiter: moderate ──
    "limiter_attack_ms": 10.0,
    "limiter_release_ms": 30.0,
    "limiter_ceiling": 0.85,
    # ── Normalisation: subtle ──
    "dynaudnorm_maxgain": 1.5,
    # ── Crossover: standard ──
    "xsplit_low_hz": 250,
    "xsplit_high_hz": 4000,
    # ── Transition timing: rolling ──
    "eq_phase_1_ratio": 0.35,
    "eq_phase_2_ratio": 0.65,
    "low_swap_beats": 1.0,
    "outro_fade_bars": 12,
}

# ──────────────────────────────────────────────
# Acid Techno
# ──────────────────────────────────────────────
# Squelchy 303 basslines, raw, hypnotic, psychedelic.
# Mid-forward for the acid line, controlled low-end.
# DR: 7-9 dB, LUFS: -7 to -9, BPM: 125-140
ACID: dict[str, Any] = {
    "hpf_cutoff_hz": 28.0,
    # ── Per-track EQ: mid-forward for 303 ──
    "per_track_eq_mid_cut_db": -0.5,  # Less cut — let 303 mids through
    "per_track_eq_bright_boost_db": 1.0,  # Bright but not harsh
    # ── Pre-compressor: light to moderate ──
    "pre_comp_threshold_db": -16.0,
    "pre_comp_ratio": 2.5,
    "pre_comp_attack_ms": 12.0,
    "pre_comp_release_ms": 100.0,
    # ── Glue compressor: gentle ──
    "glue_comp_threshold_db": -12.0,
    "glue_comp_ratio": 2.0,
    "glue_comp_attack_ms": 40.0,
    "glue_comp_release_ms": 200.0,
    # ── Master EQ: balanced, mid-forward ──
    "master_eq_air_boost_db": 1.0,
    "master_eq_mud_cut_db": -0.5,
    "master_eq_sub_boost_db": 0.5,
    # ── Limiter: gentle, preserve squelch ──
    "limiter_attack_ms": 12.0,
    "limiter_release_ms": 35.0,
    "limiter_ceiling": 0.88,
    # ── Normalisation: subtle ──
    "dynaudnorm_maxgain": 1.0,
    # ── Crossover: focus on mids where 303 lives ──
    "xsplit_low_hz": 300,
    "xsplit_high_hz": 4500,
    # ── Transition timing: slow, evolving ──
    "eq_phase_1_ratio": 0.40,
    "eq_phase_2_ratio": 0.70,
    "low_swap_beats": 1.5,  # Let acid bassline ride
    "outro_fade_bars": 16,
}

# ── Registry ──
PRESETS: dict[str, dict[str, Any]] = {
    "hypnotic": HYPNOTIC,
    "industrial": INDUSTRIAL,
    "hard": HARD,
    "dub": DUB,
    "peak_time": PEAK_TIME,
    "driving": DRIVING,
    "acid": ACID,
}

PRESET_METADATA: dict[str, dict[str, Any]] = {
    "hypnotic": {
        "label": "Hypnotic Techno",
        "bpm_range": "120-135",
        "dr_target_db": "8-12",
        "lufs_target": "-8 to -10",
        "description": "Deep, atmospheric, repetitive. Minimalist. Sub-bass focus.",
        "compression": "Light — dynamics create tension. 2.5:1 pre, 2:1 glue",
        "eq_profile": "Warm sub +1dB, gentle air +1dB, minimal mid cut -0.5dB",
        "limiter": "Gentle ceiling 0.88 (fast attack 15ms preserve punch)",
        "transition": "Slow evolution: 0.35/0.65 phase ratios, 2-beat bass swap, 16-bar outro",
    },
    "industrial": {
        "label": "Industrial Techno",
        "bpm_range": "140-155+",
        "dr_target_db": "5-7",
        "lufs_target": "-6 to -7",
        "description": "Aggressive, distorted, raw. Heavy compression, mid-range aggression.",
        "compression": "Heavy — 4:1 pre, 4:1 glue, fast attack 8ms / 20ms",
        "eq_profile": "Aggressive highs +2dB, heavy mud cut -1.5dB, minimal sub +0.3dB",
        "limiter": "Aggressive ceiling 0.80, fast attack 5ms",
        "transition": "Fast: 0.30/0.60 phase ratios, 0.5-beat bass swap, 8-bar outro",
    },
    "hard": {
        "label": "Hard Techno",
        "bpm_range": "150-160+",
        "dr_target_db": "4-6",
        "lufs_target": "-5 to -7",
        "description": "Punishing kicks, maximum punch, relentless. Schranz-influenced.",
        "compression": "Extreme — 6:1 pre, 5:1 glue, attack 5ms / 15ms",
        "eq_profile": "Piercing highs +2.5dB, maximum mud cut -2dB, kick-only sub +0.2dB",
        "limiter": "Brickwall ceiling 0.75, attack 3ms",
        "transition": "Lightning fast: 0.25/0.55 phase ratios, 0.5-beat bass swap, 4-bar outro",
    },
    "dub": {
        "label": "Dub Techno",
        "bpm_range": "120-130",
        "dr_target_db": "8-12",
        "lufs_target": "-8 to -10",
        "description": "Warm, spacious, deep. Heavy reverb/delay, minimal compression.",
        "compression": "Extremely light — 2:1 pre, 1.5:1 glue, slow attack 20ms / 50ms",
        "eq_profile": "Heavy sub +2dB, no artificial air, minimal mud cut -0.3dB",
        "limiter": "Maximum headroom ceiling 0.90, slow attack 20ms",
        "transition": "Glacial: 0.45/0.75 phase ratios, 4-beat bass swap, 24-bar outro",
    },
    "peak_time": {
        "label": "Peak-Time Techno",
        "bpm_range": "128-145",
        "dr_target_db": "6-8",
        "lufs_target": "-6 to -8",
        "description": "Big room, anthemic, relentless. Maximum energy with clarity.",
        "compression": "Moderate — 3:1 pre, 3:1 glue, standard timing",
        "eq_profile": "Open: air +2dB, sub +1dB, moderate mud cut -1dB",
        "limiter": "Moderate-aggressive ceiling 0.82, attack 8ms",
        "transition": "Driving: 0.35/0.65 phase ratios, 1-beat bass swap, 12-bar outro",
    },
    "driving": {
        "label": "Driving Techno",
        "bpm_range": "128-140",
        "dr_target_db": "6-8",
        "lufs_target": "-7 to -8",
        "description": "Forward momentum, rolling energy, steady groove. Balanced, functional.",
        "compression": "Moderate — 2.8:1 pre, 2.5:1 glue, slightly relaxed timing",
        "eq_profile": "Balanced: air +1.5dB, sub +0.8dB, moderate mud cut -0.8dB",
        "limiter": "Moderate ceiling 0.85, standard attack 10ms",
        "transition": "Rolling: 0.35/0.65 phase ratios, 1-beat bass swap, 12-bar outro",
    },
    "acid": {
        "label": "Acid Techno",
        "bpm_range": "125-140",
        "dr_target_db": "7-9",
        "lufs_target": "-7 to -9",
        "description": "Squelchy 303 basslines, raw, hypnotic, psychedelic. Mid-forward.",
        "compression": "Light-moderate — 2.5:1 pre, 2:1 glue, preserve squelch transients",
        "eq_profile": "Mid-forward: air +1dB, sub +0.5dB, minimal mud cut -0.5dB",
        "limiter": "Gentle ceiling 0.88, attack 12ms",
        "transition": "Slow evolution: 0.40/0.70 phase ratios, 1.5-beat bass swap, 16-bar outro",
    },
}
