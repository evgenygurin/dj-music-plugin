"""RimJoba Suno voice prompt recipe (Taras lock).

Spec: docs/superpowers/specs/2026-07-18-rimjoba-suno-voice-recipe-design.md
Prompt-only — no Persona/Voice create.
"""

from __future__ import annotations

from dataclasses import dataclass

REFERENCE_CLIP_ID = "e4d68e9a-d35d-4e70-8af0-4205cf484d2f"
REFERENCE_URL = f"https://suno.com/song/{REFERENCE_CLIP_ID}"

VOICE_BLOCK = (
    "RimJoba signature male voice: mid-baritone Russian rap MC, deadpan delivery, "
    "cold cocky swagger, close-mic dry presence, light autotune (subtle, not melodic robot), "
    "wide stereo ad-libs, gang-chant hooks, short delay throws on key lines, punchy consonants, "
    "relaxed jaw, half-time pocket feel even at double-time bursts, clean raw mix, "
    "intimate and arrogant at once"
)

NEGATIVE_TAGS = (
    "female vocals, choir lead, ethereal singer, opera, melodic crooner, heavy melisma, "
    "robotic extreme autotune, chipmunk, kids voice, whisper-only ASMR, folk, accordion, "
    "balalaika, orchestral lead vocal"
)

GENRE_TAILS: dict[str, str] = {
    "street_trap": (
        "Russian trap, drill-tinged hip-hop, 140 BPM, half-time bounce, booming distorted 808, "
        "punchy trap kick, triplet hi-hats, sparse dark bells, detuned synth melody, trap risers"
    ),
    "techno_rap": (
        "techno-rap, 140 BPM four-on-the-floor warehouse rave, cold synth pulse, "
        "syncopated kick-bass, sparse drums in verses, club delay throws"
    ),
    "boom_bap": (
        "boom-bap hip-hop, dusty breakbeats, swung drums, vinyl scratches, "
        "head-nod groove, sparse bass-kick-snare pocket"
    ),
    "phonk": (
        "phonk, dusty Memphis bounce, chopped cowbell groove, hard sub pulses, "
        "tape wobble, smoky half-time pocket"
    ),
    "club": (
        "Russian club-pop anthem, four-on-the-floor kick, buoyant synth stabs, "
        "chantable crowd hooks, filtered build, handclap outro"
    ),
    "late_night": (
        "jazz-hop, laid-back swung pocket, dusty brushes, upright bass, muted keys, "
        "soft sax answers, warm Rhodes"
    ),
}

LYRICS_SKELETON = """[Intro]
[deadpan, low, close mic]
Римджо́ба (эй)

[Verse 1]
[deadpan, low, close mic]
...short lines...
...end ad-libs (е) (а)

[Hook]
[cold cocky, gang doubles]
<MEM 3-6 words> (ха)
<MEM 3-6 words> (бра)
Римджо́ба — ... (эй)

[Verse 2]
...

[Hook]
...

[Outro]
...fade ad-libs (скр) (е)
"""  # noqa: RUF001


class UnknownRimJobaModeError(ValueError):
    """Raised when assemble_rimjoba_style gets an unknown genre mode."""


@dataclass(frozen=True, slots=True)
class RimJobaPrompt:
    style: str
    negative_tags: str
    mode: str
    title_prefix: str = "RimJoba"


def list_modes() -> tuple[str, ...]:
    return tuple(sorted(GENRE_TAILS))


def assemble_rimjoba_style(mode: str, *, extra_negative: str = "") -> RimJobaPrompt:
    key = mode.strip().lower().replace("-", "_").replace(" ", "_")
    tail = GENRE_TAILS.get(key)
    if tail is None:
        known = ", ".join(list_modes())
        raise UnknownRimJobaModeError(f"unknown RimJoba mode {mode!r}; known: {known}")
    style = f"{VOICE_BLOCK}. {tail}."
    negative = NEGATIVE_TAGS
    extra = extra_negative.strip()
    if extra:
        negative = f"{NEGATIVE_TAGS}, {extra}"
    return RimJobaPrompt(style=style, negative_tags=negative, mode=key)
