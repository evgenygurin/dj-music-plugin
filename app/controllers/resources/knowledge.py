"""Static knowledge resources for DJ expert sessions (knowledge:// URIs)."""

from __future__ import annotations

import json

from fastmcp.resources import resource

from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_REFERENCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.core.constants import TechnoSubgenre


@resource(
    uri="knowledge://vocabulary",
    name="DJ Vocabulary",
    title="DJ Vocabulary Map",
    description=(
        "DJ-facing vocabulary mapped to techno subgenres, BPM context, "
        "and time-of-night cues for set narrative."
    ),
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def vocabulary() -> str:
    """Return vocabulary terms with subgenre coverage and night phases."""
    data = {
        "vocabulary": [
            {
                "term": "dark",
                "subgenres": ["detroit", "industrial", "raw"],
                "bpm_range": "128-145",
                "key_features": [
                    "dissonance_mean > 0.45 — harmonic tension, no resolve",
                    "spectral_flatness > 0.22 — noise-coloured spectrum (not pure tones)",
                    "pitch_salience_mean < 0.2 — atonal or oblique melodic content",
                ],
            },
            {
                "term": "hard",
                "subgenres": ["peak_time", "hard_techno", "industrial"],
                "bpm_range": "135-155",
                "key_features": [
                    "energy_mean > 0.65 — sustained high RMS pressure",
                    "kick_prominence > 0.75 — kick dominates the mix",
                    "integrated_lufs > -9 LUFS — loud, limited dynamics",
                ],
            },
            {
                "term": "hypnotic",
                "subgenres": ["hypnotic", "minimal", "detroit"],
                "bpm_range": "125-134",
                "key_features": [
                    "energy_std < 0.14 — flat, unwavering level across the track",
                    "spectral_flux_std < 0.9 — stable timbral texture (loop-lock feel)",
                    "bpm_stability > 0.92 — ultra-rigid grid, no swing or drift",
                ],
            },
            {
                "term": "acid",
                "subgenres": ["acid"],
                "bpm_range": "130-140",
                "key_features": [
                    "spectral_centroid_hz > 2500 Hz — 303-like high-frequency presence",
                    "dissonance_mean > 0.45 — squelch and resonant filter movement",
                    "spectral_complexity_mean > 13 — rich harmonic content from sweeps",
                ],
            },
            {
                "term": "melodic",
                "subgenres": ["melodic_deep", "progressive"],
                "bpm_range": "122-132",
                "key_features": [
                    "pitch_salience_mean > 0.4 — clear, recognisable melody or lead",
                    "spectral_flatness < 0.13 — tonal spectrum (harmonic content dominates)",
                    "energy_slope > 0 — progressive build arc across the track",
                ],
            },
            {
                "term": "atmospheric",
                "subgenres": ["ambient_dub", "dub_techno"],
                "bpm_range": "115-128",
                "key_features": [
                    "energy_mean < 0.3 — low RMS, generous headroom",
                    "loudness_range_lu > 8 LU — wide dynamic swing (space and silence)",
                    "spectral_centroid_hz < 1800 Hz — warm, low-mid colour palette",
                ],
            },
            {
                "term": "driving",
                "subgenres": ["driving", "tribal", "peak_time"],
                "bpm_range": "128-138",
                "key_features": [
                    "danceability > 2.2 — high groove coefficient, locked floor feel",
                    "pulse_clarity > 0.55 — beat is unambiguous at floor SPL",
                    "bpm_stability > 0.9 — straight-time grid, no hesitation",
                ],
            },
            {
                "term": "groovy",
                "subgenres": ["tribal", "breakbeat"],
                "bpm_range": "126-140",
                "key_features": [
                    "onset_rate > 3.5/bar — dense percussion events (polyrhythm or breaks)",
                    "bpm_stability < 0.85 — loose grid, swing or break feel",
                    "dynamic_complexity > 0.3 — rhythmic variation creates body movement",
                ],
            },
            {
                "term": "raw",
                "subgenres": ["raw", "industrial"],
                "bpm_range": "135-150",
                "key_features": [
                    "spectral_flatness > 0.23 — noise-heavy, distorted texture",
                    "dissonance_mean > 0.4 — harsh timbral clash, no polish",
                    "crest_factor_db < 7 dB — brick-walled, transients crushed",
                ],
            },
            {
                "term": "deep",
                "subgenres": ["dub_techno", "minimal"],
                "bpm_range": "120-130",
                "key_features": [
                    "energy_low > 0.15 — sub and low-bass presence anchors the mix",
                    "spectral_complexity_mean < 10 — sparse arrangement, few elements",
                    "loudness_range_lu > 7 LU — room to breathe, dynamics intact",
                ],
            },
        ],
        "time_of_night": [
            {
                "window": "21:00-23:00",
                "phase": "doors",
                "energy": "low",
                "templates": ["warm_up"],
                "energy_guidance": (
                    "ambient_dub, dub_techno — wide dynamics, no peaks, invite curiosity."
                ),
            },
            {
                "window": "23:00-01:00",
                "phase": "warm_up",
                "energy": "rising",
                "templates": ["warm_up", "journey"],
                "energy_guidance": (
                    "minimal, detroit, melodic_deep — build pocket and trust, avoid peak clichés."
                ),
            },
            {
                "window": "01:00-03:00",
                "phase": "build",
                "energy": "high-rising",
                "templates": ["peak_hour", "journey"],
                "energy_guidance": (
                    "progressive, hypnotic, driving — increase density, 16-bar phrase lock."
                ),
            },
            {
                "window": "03:00-05:00",
                "phase": "peak",
                "energy": "high",
                "templates": ["peak_hour"],
                "energy_guidance": (
                    "peak_time, acid, tribal — reward releases,"
                    " phrase discipline, selective valleys."
                ),
            },
            {
                "window": "05:00-07:00",
                "phase": "closing",
                "energy": "resolution",
                "templates": ["closing"],
                "energy_guidance": (
                    "raw, industrial, hard_techno or back to dub/minimal"
                    " — longer blends, leave a memory."
                ),
            },
        ],
    }
    return json.dumps(data, indent=2)


def _subgenre_culture_entries() -> list[dict[str, object]]:
    # Artists verified against Resident Advisor, iMusician, and samplesoundmusic.com guides
    artists_by_subgenre: dict[TechnoSubgenre, list[str]] = {
        TechnoSubgenre.AMBIENT_DUB: ["Deepchord", "Porter Ricks", "Biosphere"],
        TechnoSubgenre.DUB_TECHNO: ["Basic Channel", "DeepChord", "Echospace"],
        TechnoSubgenre.MINIMAL: ["Richie Hawtin", "Ricardo Villalobos", "Robert Hood"],
        TechnoSubgenre.DETROIT: ["Underground Resistance", "Derrick May", "Juan Atkins"],
        TechnoSubgenre.MELODIC_DEEP: ["Stephan Bodzin", "Tale Of Us", "ARTBAT"],
        TechnoSubgenre.PROGRESSIVE: ["Sasha", "John Digweed", "Hernan Cattaneo"],
        TechnoSubgenre.HYPNOTIC: ["Donato Dozzy", "Voices From The Lake", "Inland"],
        TechnoSubgenre.DRIVING: ["Ben Klock", "Marcel Dettmann", "Blawan"],
        TechnoSubgenre.TRIBAL: ["Len Faki", "SPFDJ", "Rebekah"],
        TechnoSubgenre.BREAKBEAT: ["Surgeon", "Oscar Mulero", "Objekt"],
        TechnoSubgenre.PEAK_TIME: ["Adam Beyer", "Charlotte de Witte", "Enrico Sangiuliano"],
        TechnoSubgenre.ACID: ["Hardfloor", "Josh Wink", "Thomas P. Heckmann"],
        TechnoSubgenre.RAW: ["Dax J", "I Hate Models", "Developer"],
        TechnoSubgenre.INDUSTRIAL: ["Ancient Methods", "Perc", "SHXCXCHCXSH"],
        TechnoSubgenre.HARD_TECHNO: ["Paula Temple", "Viper XXL", "Nico Moreno"],
    }
    labels_by_subgenre: dict[TechnoSubgenre, list[str]] = {
        TechnoSubgenre.AMBIENT_DUB: ["Chain Reaction", "Echospace Detroit", "Glacial Movements"],
        TechnoSubgenre.DUB_TECHNO: [
            "Basic Channel / Rhythm & Sound",
            "Mille Plateaux",
            "Deepchord Recordings",
        ],
        TechnoSubgenre.MINIMAL: ["Perlon", "Cocoon", "M_nus"],
        TechnoSubgenre.DETROIT: ["Transmat", "Metroplex", "M-Plant"],
        TechnoSubgenre.MELODIC_DEEP: ["Afterlife", "Stil vor Talent", "RYNX"],
        TechnoSubgenre.PROGRESSIVE: ["Bedrock", "Global Underground", "Yoshitoshi"],
        TechnoSubgenre.HYPNOTIC: ["Spazio Disponibile", "Prologue", "Semantica"],
        TechnoSubgenre.DRIVING: ["Ostgut Ton", "Berceuse Heroique", "Perc Trax"],
        TechnoSubgenre.TRIBAL: ["CLR", "Second State", "Tresor"],
        TechnoSubgenre.BREAKBEAT: ["Blueprint", "Token", "Houndstooth"],
        TechnoSubgenre.PEAK_TIME: ["Drumcode", "Filth on Acid", "We Are The Brave"],
        TechnoSubgenre.ACID: ["Acid Test", "Balkan Vinyl", "Klakson"],
        TechnoSubgenre.RAW: ["MORD", "Stroboscopic Artefacts", "Infrastructure New York"],
        TechnoSubgenre.INDUSTRIAL: ["Downwards", "Sonic Groove", "Perc Trax"],
        TechnoSubgenre.HARD_TECHNO: ["NineTimesNine", "Possession", "BFDM"],
    }
    position_hint: dict[TechnoSubgenre, str] = {
        TechnoSubgenre.AMBIENT_DUB: "opening / breathing room / after-party",
        TechnoSubgenre.DUB_TECHNO: "early warm-up depth (21:00-23:00)",
        TechnoSubgenre.MINIMAL: "mid warm-up micro-groove (23:00-01:00)",
        TechnoSubgenre.DETROIT: "warm-up to mid-set soul (23:00-02:00)",
        TechnoSubgenre.MELODIC_DEEP: "emotional mid arcs / festival sunrise",
        TechnoSubgenre.PROGRESSIVE: "long-form builds / extended set journey",
        TechnoSubgenre.HYPNOTIC: "sustained mid-roller / 01:00-03:00 trance zone",
        TechnoSubgenre.DRIVING: "main floor traction (02:00-04:00)",
        TechnoSubgenre.TRIBAL: "percussive peaks / bridges between energy levels",
        TechnoSubgenre.BREAKBEAT: "contrast windows / rhythmic resets",
        TechnoSubgenre.PEAK_TIME: "peak hour anthems (03:00-05:00)",
        TechnoSubgenre.ACID: "peak spice / late-night psychedelic injection",
        TechnoSubgenre.RAW: "late intensity / 04:00-06:00 grind",
        TechnoSubgenre.INDUSTRIAL: "late edge / pressure / warehouse finales",
        TechnoSubgenre.HARD_TECHNO: "closing sprint (05:00+) / dedicated hard-techno blocks",
    }
    # Musically meaningful flows based on energy proximity and cultural adjacency.
    # flows_from = subgenres that typically precede this one in a set.
    # flows_into = subgenres that typically follow.
    flows_from_map: dict[TechnoSubgenre, list[str]] = {
        TechnoSubgenre.AMBIENT_DUB: [],
        TechnoSubgenre.DUB_TECHNO: ["ambient_dub"],
        TechnoSubgenre.MINIMAL: ["dub_techno", "detroit"],
        TechnoSubgenre.DETROIT: ["minimal", "dub_techno"],
        TechnoSubgenre.MELODIC_DEEP: ["detroit", "progressive"],
        TechnoSubgenre.PROGRESSIVE: ["melodic_deep", "detroit"],
        TechnoSubgenre.HYPNOTIC: ["minimal", "detroit", "driving"],
        TechnoSubgenre.DRIVING: ["hypnotic", "detroit", "progressive"],
        TechnoSubgenre.TRIBAL: ["driving", "hypnotic"],
        TechnoSubgenre.BREAKBEAT: ["tribal", "driving"],
        TechnoSubgenre.PEAK_TIME: ["driving", "tribal", "acid"],
        TechnoSubgenre.ACID: ["peak_time", "breakbeat"],
        TechnoSubgenre.RAW: ["acid", "industrial"],
        TechnoSubgenre.INDUSTRIAL: ["raw", "peak_time"],
        TechnoSubgenre.HARD_TECHNO: ["industrial", "raw", "peak_time"],
    }
    flows_into_map: dict[TechnoSubgenre, list[str]] = {
        TechnoSubgenre.AMBIENT_DUB: ["dub_techno"],
        TechnoSubgenre.DUB_TECHNO: ["minimal", "detroit", "ambient_dub"],
        TechnoSubgenre.MINIMAL: ["detroit", "hypnotic", "dub_techno"],
        TechnoSubgenre.DETROIT: ["minimal", "hypnotic", "melodic_deep", "progressive"],
        TechnoSubgenre.MELODIC_DEEP: ["progressive", "detroit", "hypnotic"],
        TechnoSubgenre.PROGRESSIVE: ["driving", "detroit", "melodic_deep"],
        TechnoSubgenre.HYPNOTIC: ["driving", "minimal", "tribal"],
        TechnoSubgenre.DRIVING: ["tribal", "peak_time", "hypnotic"],
        TechnoSubgenre.TRIBAL: ["driving", "breakbeat", "peak_time"],
        TechnoSubgenre.BREAKBEAT: ["tribal", "acid", "driving"],
        TechnoSubgenre.PEAK_TIME: ["industrial", "acid", "hard_techno"],
        TechnoSubgenre.ACID: ["peak_time", "industrial", "breakbeat"],
        TechnoSubgenre.RAW: ["industrial", "hard_techno"],
        TechnoSubgenre.INDUSTRIAL: ["raw", "hard_techno", "peak_time"],
        TechnoSubgenre.HARD_TECHNO: ["industrial", "raw"],
    }
    entries: list[dict[str, object]] = []
    for sg in TechnoSubgenre:
        entries.append(
            {
                "name": sg.value,
                "artists": artists_by_subgenre[sg],
                "labels": labels_by_subgenre[sg],
                "set_position": position_hint[sg],
                "flows_from": flows_from_map[sg],
                "flows_into": flows_into_map[sg],
            }
        )
    return entries


@resource(
    uri="knowledge://subgenre-culture",
    name="Subgenre Culture",
    title="Techno Subgenre Culture",
    description="Artists, labels, set roles, and low/high-energy flow hints per subgenre.",
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def subgenre_culture() -> str:
    data = {"subgenres": _subgenre_culture_entries()}
    return json.dumps(data, indent=2)


@resource(
    uri="knowledge://set-dynamics",
    name="Set Dynamics",
    title="Set Dynamics and Phrasing",
    description="Energy arcs, tension cycles, and phrase-aware DJing heuristics.",
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def set_dynamics() -> str:
    data = {
        "mix_structure_arc": {
            "phases": [
                {
                    "phase": "warm_up",
                    "energy": "low → medium",
                    "goal": "Set mood, invite listeners in",
                    "track_traits": "Deep, spacey, few hooks — ambient_dub, dub_techno, minimal",
                    "transition_focus": "Long blends (32-64 bars), gentle EQ rides, no drops",
                },
                {
                    "phase": "build",
                    "energy": "medium rising",
                    "goal": "Increase intensity, commit the floor",
                    "track_traits": (
                        "Stronger drums, groove density up — detroit, hypnotic, progressive"
                    ),
                    "transition_focus": "Tight beatmatching, layering extra percussion in",
                },
                {
                    "phase": "peak",
                    "energy": "high",
                    "goal": "Hit the major high point, maximum floor engagement",
                    "track_traits": "Heavy drops, dense arrangements — peak_time, acid, tribal",
                    "transition_focus": "Short impactful switches (8-16 bars), quick blends",
                },
                {
                    "phase": "release",
                    "energy": "medium",
                    "goal": "Let the crowd breathe without losing momentum",
                    "track_traits": "Melodic or vocal tracks, breakdowns — driving, detroit",
                    "transition_focus": "Longer breakdowns, filters, reverb/echo tails",
                },
                {
                    "phase": "finale",
                    "energy": "medium dropping",
                    "goal": "Land the story with a memorable close",
                    "track_traits": (
                        "Emotional or familiar, slower groove — raw, industrial, or back to dub"
                    ),
                    "transition_focus": "Extended outro loops, echo out, fade to silence",
                },
            ],
        },
        "twenty_minute_rule": {
            "summary": "Audiences metabolize timbre and loudness roughly every 18-22 minutes.",
            "practice": (
                "Change primary texture, harmonic centre, or groove density "
                "before fatigue sets in."
            ),
        },
        "energy_arc": {
            "macro": "Low → ramp → plateau → selective valleys → resolution.",
            "micro": "Use 8/16/32 bar windows to mirror phrase boundaries.",
            "contrast_principle": (
                "Sustained peak intensity fatigues ears. Intentional lower-energy"
                " sections after major moments restore engagement headroom."
            ),
        },
        "tension_release_cycles": {
            "micro": (
                "Within a single transition: filter closed → add percussion → remove filter "
                "→ full blend. Delayed resolution builds anticipation."
            ),
            "macro": (
                "Across the whole set: build (filter closed, fewer highs) "
                "→ small release → bigger build → main release → valley → final climb."
            ),
            "pitfall": (
                "Stacking full drops back-to-back without contrast reads as flat loudness. "
                "A 4-minute drop needs a 2-minute valley before the next one lands."
            ),
        },
        "phrase_awareness": {
            "definition": "Musical paragraphs in techno align with 16/32 bar multiples.",
            "rule": "Start an incoming track at the beginning of a phrase (bar 1 or 17 or 33).",
            "benefit": "Preserves groove memory; misaligned entries sound 'broken'.",
            "breakbeat_exception": (
                "Breakbeat/tribal tracks may use intentional off-phrase drops for energy shock."
            ),
        },
        "harmonic_mixing": {
            "rule": (
                "Compatible Camelot keys for long blends;"
                " percussion-led tracks tolerate more dissonance."
            ),
            "energy_lift": (
                "Move up 1-2 Camelot steps (e.g. 8A → 9A) before a drop for perceived energy lift."
            ),
            "club_reality": (
                "Harmonic clashes matter most when harmonic elements (pads, vocals) are exposed."
            ),
        },
        "hard_rules": {
            "kick_alignment": "Prefer mixing on downbeats when both tracks are four-on-the-floor.",
            "bpm_delta_rule": "BPM jumps > 5 need shorter blends or rhythmic bridge material.",
            "groove_compatibility": (
                "Straight-timed and swung tracks clash on long overlaps — use short cuts."
            ),
        },
    }
    return json.dumps(data, indent=2)


@resource(
    uri="knowledge://dancefloor-psychology",
    name="Dancefloor Psychology",
    title="Dancefloor Psychology",
    description="Crowd state models, recovery, and how harmony is perceived on a loud floor.",
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def dancefloor_psychology() -> str:
    data = {
        "crowd_states": {
            "scanning": {
                "description": "Listeners evaluate safety, tempo, and social vibe.",
                "what_works": "Familiar rhythmic language, moderate BPM, open space in the mix.",
                "avoid": "Sudden aggression, disorientating key changes, excessive reverb.",
            },
            "warming": {
                "description": "Physical movement begins; trust in the DJ established.",
                "what_works": "Groove-forward tracks, pocket over complexity, subtle tension.",
                "avoid": "Premature peaks; they signal the set has nowhere to go.",
            },
            "locked_in": {
                "description": "Coordinated movement, altered perception — the 'zone'.",
                "what_works": "Small changes read clearly; repetition is reward, not boredom.",
                "avoid": "Jarring non-phrase entries that break flow memory.",
            },
            "peak_state": {
                "description": "Adrenaline, collective euphoria, maximum floor engagement.",
                "what_works": (
                    "Heavy kicks, clear drops, acid lines, short tension-release cycles."
                ),
                "avoid": "Melodic content that breaks the trance; abrupt slowdowns.",
            },
            "overstimulated": {
                "description": "Ear fatigue; highs feel harsh; micro-timing slips.",
                "what_works": "Energy valley — dub moment, stripped percussion, filter-down.",
                "avoid": "More of the same; the next peak needs contrast to land.",
            },
        },
        "energy_recovery": {
            "tools": [
                "Filter down highs gradually over 16 bars",
                "Strip to kick and sub only",
                "Full breakdown — no kick for 8 bars",
                "Dub/ambient interlude (1-2 tracks)",
            ],
            "goal": "Restore ear headroom before the next peak so it feels twice as big.",
            "timing": (
                "After 20-30 minutes of sustained peak, a 4-8 minute valley is a floor investment."
            ),
        },
        "harmonic_mixing_perception": {
            "club_reality": (
                "At 100+ dB, harmonic relationships matter most"
                " in exposed layers (pads, vocals, leads)."
            ),
            "bass_clash_rule": (
                "Two basslines a semitone apart create audible beating"
                " — use EQ or shorter overlap."
            ),
            "camelot": (
                "Compatible keys for blends > 32 bars;"
                " percussion-led tracks tolerate more dissonance."
            ),
            "energy_lift_trick": (
                "Transition to a track 1 Camelot step up"
                " for a perceived energy +5% without BPM change."
            ),
        },
        "techno_specific": {
            "darkness_appeal": (
                "Darkness in techno is not aggression"
                " — it is release from social performance. Embrace it."
            ),
            "repetition_as_hypnosis": (
                "16+ bar repetition with micro-variation is neurologically"
                " trance-inducing. Don't rush it."
            ),
            "space_as_tension": (
                "Silence, sub drops, and filtered moments"
                " create more tension than adding elements."
            ),
            "warehouse_vs_festival": (
                "Warehouse crowds reward patience and depth; festival crowds need"
                " more frequent peaks and recognisable moments."
            ),
        },
    }
    return json.dumps(data, indent=2)
