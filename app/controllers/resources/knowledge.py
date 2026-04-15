"""Static knowledge resources for DJ expert sessions (knowledge:// URIs)."""

from __future__ import annotations

import json

from fastmcp.resources import resource

from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_REFERENCE,
    RESOURCE_META,
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
                    "Minor tonal bias",
                    "Reduced highs / shadowy spectrum",
                    "Tension without obvious euphoria",
                ],
            },
            {
                "term": "hard",
                "subgenres": ["peak_time", "hard_techno", "industrial"],
                "bpm_range": "135-155",
                "key_features": [
                    "High kick density",
                    "Compressed dynamics",
                    "Forward pressure on the floor",
                ],
            },
            {
                "term": "hypnotic",
                "subgenres": ["hypnotic", "minimal", "detroit"],
                "bpm_range": "125-134",
                "key_features": [
                    "Loop stability",
                    "Micro-variation over long phrases",
                    "Trance-inducing repetition",
                ],
            },
            {
                "term": "acid",
                "subgenres": ["acid"],
                "bpm_range": "132-140",
                "key_features": [
                    "Resonant 303 motion",
                    "Squelch and filter sweeps",
                    "High timbral brightness peaks",
                ],
            },
            {
                "term": "melodic",
                "subgenres": ["melodic_deep", "progressive"],
                "bpm_range": "122-132",
                "key_features": [
                    "Harmonic hooks",
                    "Long evolving pads or leads",
                    "Emotional contour in the mix",
                ],
            },
            {
                "term": "atmospheric",
                "subgenres": ["ambient_dub", "dub_techno"],
                "bpm_range": "120-128",
                "key_features": [
                    "Space and reverb tails",
                    "Low percussive density",
                    "Wide stereo field",
                ],
            },
            {
                "term": "driving",
                "subgenres": ["driving", "tribal", "peak_time"],
                "bpm_range": "128-138",
                "key_features": [
                    "Four-on-the-floor dominance",
                    "Clear pulse grid",
                    "Floor-forward momentum",
                ],
            },
            {
                "term": "groovy",
                "subgenres": ["tribal", "breakbeat"],
                "bpm_range": "126-140",
                "key_features": [
                    "Percussion-led pocket",
                    "Swing or broken grid contrast",
                    "Body-first movement cues",
                ],
            },
            {
                "term": "raw",
                "subgenres": ["raw", "industrial"],
                "bpm_range": "135-150",
                "key_features": [
                    "Distorted drums and mids",
                    "Aggressive transients",
                    "Unpolished timbral edge",
                ],
            },
            {
                "term": "deep",
                "subgenres": ["dub_techno", "minimal"],
                "bpm_range": "122-130",
                "key_features": [
                    "Sub-bass weight",
                    "Sparse arrangement",
                    "Horizontal time feel",
                ],
            },
        ],
        "time_of_night": [
            {
                "phase": "doors",
                "energy": "low",
                "guidance": "Wide dynamics, fewer peaks; invite curiosity.",
            },
            {
                "phase": "warm_up",
                "energy": "rising",
                "guidance": "Avoid peak-time clichés; build pocket and trust.",
            },
            {
                "phase": "peak",
                "energy": "high",
                "guidance": "Phrase discipline; reward releases without fatiguing highs.",
            },
            {
                "phase": "closing",
                "energy": "resolution",
                "guidance": "Longer blends, harmonic kindness, leave a memory not a hangover.",
            },
        ],
    }
    return json.dumps(data, indent=2)


def _subgenre_culture_entries() -> list[dict[str, object]]:
    ordered = list(TechnoSubgenre)
    artists_by_subgenre: dict[TechnoSubgenre, list[str]] = {
        TechnoSubgenre.AMBIENT_DUB: ["Deepchord", "Porter Ricks"],
        TechnoSubgenre.DUB_TECHNO: ["Basic Channel", "Maurizio"],
        TechnoSubgenre.MINIMAL: ["Ricardo Villalobos", "Zip"],
        TechnoSubgenre.DETROIT: ["Underground Resistance", "Robert Hood"],
        TechnoSubgenre.MELODIC_DEEP: ["Stephan Bodzin", "Tale Of Us"],
        TechnoSubgenre.PROGRESSIVE: ["Sasha", "John Digweed"],
        TechnoSubgenre.HYPNOTIC: ["Donato Dozzy", "Voices From The Lake"],
        TechnoSubgenre.DRIVING: ["Ben Klock", "Marcel Dettmann"],
        TechnoSubgenre.TRIBAL: ["Len Faki", "Chris Liebing"],
        TechnoSubgenre.BREAKBEAT: ["Surgeon", "Oscar Mulero"],
        TechnoSubgenre.PEAK_TIME: ["Adam Beyer", "Amelie Lens"],
        TechnoSubgenre.ACID: ["Hardfloor", "Josh Wink"],
        TechnoSubgenre.RAW: ["Dax J", "I Hate Models"],
        TechnoSubgenre.INDUSTRIAL: ["Ancient Methods", "Regis"],
        TechnoSubgenre.HARD_TECHNO: ["DJK", "Nico Moreno"],
    }
    labels_by_subgenre: dict[TechnoSubgenre, list[str]] = {
        TechnoSubgenre.AMBIENT_DUB: ["Chain Reaction", "Echospace"],
        TechnoSubgenre.DUB_TECHNO: ["Hardwax", "Rhythm & Sound"],
        TechnoSubgenre.MINIMAL: ["Perlon", "Cocoon"],
        TechnoSubgenre.DETROIT: ["Transmat", "M-Plant"],
        TechnoSubgenre.MELODIC_DEEP: ["Afterlife", "Stil vor Talent"],
        TechnoSubgenre.PROGRESSIVE: ["Bedrock", "GU"],
        TechnoSubgenre.HYPNOTIC: ["Spazio Disponibile", "Prologue"],
        TechnoSubgenre.DRIVING: ["Ostgut Ton", "Drumcode"],
        TechnoSubgenre.TRIBAL: ["CLR", "Second State"],
        TechnoSubgenre.BREAKBEAT: ["Blueprint", "Token"],
        TechnoSubgenre.PEAK_TIME: ["Filth on Acid", "We Are The Brave"],
        TechnoSubgenre.ACID: ["Acid Test", "Balkan Vinyl"],
        TechnoSubgenre.RAW: ["RAW", "MORD"],
        TechnoSubgenre.INDUSTRIAL: ["Downwards", "Hospital Productions"],
        TechnoSubgenre.HARD_TECHNO: ["NineTimesNine", "Possession"],
    }
    position_hint: dict[TechnoSubgenre, str] = {
        TechnoSubgenre.AMBIENT_DUB: "opening / breathing room",
        TechnoSubgenre.DUB_TECHNO: "early warm-up depth",
        TechnoSubgenre.MINIMAL: "mid warm-up micro-groove",
        TechnoSubgenre.DETROIT: "warm-up to mid-set soul",
        TechnoSubgenre.MELODIC_DEEP: "emotional mid arcs",
        TechnoSubgenre.PROGRESSIVE: "long-form builds",
        TechnoSubgenre.HYPNOTIC: "sustained mid-roller",
        TechnoSubgenre.DRIVING: "main floor traction",
        TechnoSubgenre.TRIBAL: "percussive peaks or bridges",
        TechnoSubgenre.BREAKBEAT: "contrast windows / resets",
        TechnoSubgenre.PEAK_TIME: "peak hour anthems",
        TechnoSubgenre.ACID: "peak or late spice",
        TechnoSubgenre.RAW: "late intensity",
        TechnoSubgenre.INDUSTRIAL: "late edge / pressure",
        TechnoSubgenre.HARD_TECHNO: "closing sprint or dedicated hard blocks",
    }
    entries: list[dict[str, object]] = []
    for i, sg in enumerate(ordered):
        prev_vals = [ordered[i - 1].value] if i > 0 else []
        next_vals = [ordered[i + 1].value] if i < len(ordered) - 1 else []
        entries.append(
            {
                "name": sg.value,
                "artists": artists_by_subgenre[sg],
                "labels": labels_by_subgenre[sg],
                "set_position": position_hint[sg],
                "flows_from": prev_vals,
                "flows_into": next_vals,
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
)
async def set_dynamics() -> str:
    data = {
        "twenty_minute_rule": {
            "summary": ("Audiences metabolize timbre and loudness roughly every 18-22 minutes."),
            "practice": (
                "Change primary texture, harmonic center, or groove density "
                "before fatigue sets in."
            ),
        },
        "energy_arc": {
            "macro": "Low → ramp → plateau → selective valleys → resolution.",
            "micro": "Use 8/16/32 bar windows to mirror phrase boundaries.",
        },
        "tension_release_cycles": {
            "pattern": (
                "Build (filter closed, fewer highs) → small release → bigger build → main release."
            ),
            "pitfall": (
                "Stacking full drops back-to-back without contrast reads as flat loudness."
            ),
        },
        "hard_rules": {
            "kick_alignment": "Prefer mixing on downbeats when both tracks are four-on-the-floor.",
            "bpm_delta": "Large BPM jumps need shorter blends or rhythmic bridge material.",
        },
        "phrase_awareness": {
            "definition": "Musical paragraphs usually align with 16/32 bar multiples in techno.",
            "benefit": "Mixing in/out on phrase boundaries preserves groove memory.",
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
)
async def dancefloor_psychology() -> str:
    data = {
        "crowd_states": {
            "scanning": "Listeners evaluate safety, tempo, and social vibe.",
            "locked_in": "Coordinated movement; small changes read clearly.",
            "overstimulated": "Ear fatigue; highs feel harsh; micro-timing slips.",
        },
        "energy_recovery": {
            "tools": ["Filter down highs", "Strip to percussion", "Breakdown or dub moment"],
            "goal": "Restore headroom before the next peak.",
        },
        "harmonic_mixing_perception": {
            "club_reality": "Harmonic relationships matter most in exposed harmonic layers.",
            "camelot": "Use compatible keys for long blends; percussion-led tracks forgive more.",
        },
    }
    return json.dumps(data, indent=2)
