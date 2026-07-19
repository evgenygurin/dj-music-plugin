# ruff: noqa: RUF001

"""Swallow Boy voice target and short-form variant set.

Reference-led voice ladder for Suno v5.5 Pro / chirp-fenix.
"""

from __future__ import annotations

from dataclasses import dataclass

SWALLOW_BOY_REFERENCE_CLIP_ID = "ed011c66-bd94-4bb2-bfd8-ec96a78ddc93"
SWALLOW_BOY_REFERENCE_URL = f"https://suno.com/song/{SWALLOW_BOY_REFERENCE_CLIP_ID}"

SWALLOW_BOY_VOICE_CORE = (
    "Swallow Boy signature male Russian rap lead, mid-to-low baritone, close-mic dry intimacy, "
    "restrained confident delivery, understated deadpan control, consistent throat color, "
    "punchy consonants, clear diction, light autotune only, intimate center lead, "
    "no theatrical oversing, portable across genres"
)

SWALLOW_BOY_NEGATIVE = (
    "female lead, choir lead, ethereal singer, crooner melisma, opera, theatrical oversing, "
    "heavy robotic autotune, chipmunk, kid voice, bright EDM diva top line, "
    "long cinematic intro, long outro"
)


@dataclass(frozen=True, slots=True)
class VoiceVariant:
    variant_id: str
    title_hint: str
    twist: str
    genre_tail: str
    lyrics: str


@dataclass(frozen=True, slots=True)
class SwallowBoyPrompt:
    variant: VoiceVariant
    style: str
    negative_tags: str
    model: str = "chirp-fenix"


class UnknownSwallowBoyVariantError(ValueError):
    """Raised when a variant_id is unknown."""


SWALLOW_BOY_VARIANTS: tuple[VoiceVariant, ...] = (
    VoiceVariant(
        variant_id="deadpan_baritone",
        title_hint="Deadpan Baritone",
        twist="flat low baritone, almost spoken, zero smile, pure dry room realism",
        genre_tail="minimal dark trap beat, sparse 808, 90 BPM half-time, no bright hats",
        lyrics="""[Verse]
[deadpan, low, close mic]
Тише. Без шума (е)
Ровно. По делу (а)
Swallow Boy на связи (эй)
Слово — как гвоздь (ха)""",
    ),
    VoiceVariant(
        variant_id="restrained_confident",
        title_hint="Restrained Confident",
        twist="controlled confident male lead, understated swagger, no cartoon bravado",
        genre_tail="Russian trap, 140 BPM half-time, dark bells, clean low end",
        lyrics="""[Hook]
[controlled, dry]
Swallow Boy — ровный тон (эй)
Swallow Boy — держит дом (а)
Без истерик. Только вес (ха)
Тихий голос режет лес (скр)""",
    ),
    VoiceVariant(
        variant_id="whisper_intimate",
        title_hint="Whisper Intimate",
        twist="near-whisper intimate threat, still clear diction, dark chest air",
        genre_tail="ambient trap, sub pulse, no long intro, 86 BPM",
        lyrics="""[Verse]
[whisper, close mic]
Дверь закрыта. Свет погас (е)
Слышь дыханье. Это бас (а)
Swallow Boy. Без витрин (эй)
Только голос. Только дым (ха)""",
    ),
    VoiceVariant(
        variant_id="gritty_controlled",
        title_hint="Gritty Controlled",
        twist="slight throat grit, controlled compression, no blown-out distortion",
        genre_tail="phonk shell, chopped cowbell, hard sub, smoky half-time",
        lyrics="""[Hook]
[gritty, dry]
Низкий ток и тёмный блок (эй)
Swallow Boy — короткий ток (а)
Пыльный воздух, острый слог (ха)
Всё по делу. Без тревог (скр)""",
    ),
    VoiceVariant(
        variant_id="dry_podcast_rap",
        title_hint="Dry Podcast Rap",
        twist="ultra dry center lead, podcast intimacy, barely any room",
        genre_tail="sparse piano trap, intimate, 92 BPM",
        lyrics="""[Verse]
[dry close mic]
Я не громкий. Я прямой (е)
Каждый слог — как нож живой (а)
Swallow Boy читает в лоб (эй)
Без декора. Только ток (ха)""",
    ),
    VoiceVariant(
        variant_id="light_at_hook",
        title_hint="Light AT Hook",
        twist="rap lead with subtle autotuned hook, still male rap not pop singer",
        genre_tail="melodic trap, minor synth, half-time bounce, short hook focus",
        lyrics="""[Hook]
[light autotune, restrained]
Ночь не спит. И я не сплю (эй)
Swallow Boy — иду в нулю (а)
Тихий тон, но бьёт в висок (ха)
Слишком близко. Слишком впрок (скр)""",
    ),
    VoiceVariant(
        variant_id="boom_bap_diction",
        title_hint="Boom Bap Diction",
        twist="old-school articulation, consonant-forward diction, dry head-nod pocket",
        genre_tail="boom-bap, dusty breakbeat, vinyl scratch, no choir",
        lyrics="""[Verse]
[boom-bap pocket]
Пыль на сэмпле. Ровный шаг (е)
Слово держит. Это факт (а)
Swallow Boy не льёт туман (эй)
Каждый слог — как чистый план (ха)""",
    ),
    VoiceVariant(
        variant_id="warehouse_timing",
        title_hint="Warehouse Timing",
        twist="precise on-grid warehouse rap timing, cold but not shouted",
        genre_tail="techno-rap, 140 BPM four-on-the-floor, warehouse pulse",
        lyrics="""[Hook]
[on-grid, cold]
Пульт и голос — в один шов (эй)
Swallow Boy — без лишних слов (а)
Сто сорок в полу и грудь (ха)
Темный зал и ровный путь (скр)""",
    ),
    VoiceVariant(
        variant_id="nasal_modern_edge",
        title_hint="Nasal Modern Edge",
        twist="slight nasal modern RU rap edge, tight jaw, compact vowels",
        genre_tail="modern Russian rap, hard kick, rolling hats, 95 BPM",
        lyrics="""[Verse]
[modern compact]
Город слышит этот нос (е)
Слишком близко. Без вопросов (а)
Swallow Boy — как шрам на бит (эй)
Тихий тембр, а зал кипит (ха)""",
    ),
    VoiceVariant(
        variant_id="reference_clone_control",
        title_hint="Reference Clone Control",
        twist=(
            "closest possible restrained clone of the reference voice target, "
            "same low male center, same emotional temperature"
        ),
        genre_tail="neutral dark rap shell, no flashy production, voice showcase only",
        lyrics="""[Verse]
[reference control, dry]
Голос низкий. Воздух сух (е)
Слоги давят прямо в слух (а)
Swallow Boy — без лишних поз (эй)
Только тембр. И только вес (ха)""",
    ),
)


def get_swallow_boy_variant(variant_id: str) -> VoiceVariant:
    key = variant_id.strip().lower().replace("-", "_").replace(" ", "_")
    for variant in SWALLOW_BOY_VARIANTS:
        if variant.variant_id == key:
            return variant
    known = ", ".join(variant.variant_id for variant in SWALLOW_BOY_VARIANTS)
    raise UnknownSwallowBoyVariantError(
        f"unknown swallow boy variant {variant_id!r}; known: {known}"
    )


def assemble_swallow_boy_prompt(variant_id: str) -> SwallowBoyPrompt:
    variant = get_swallow_boy_variant(variant_id)
    style = (
        f"{SWALLOW_BOY_VOICE_CORE}. "
        f"Vocal variant: {variant.twist}. "
        f"{variant.genre_tail}. "
        "Short clip under 35 seconds, fast vocal entry, no long intro, no long outro."
    )
    return SwallowBoyPrompt(variant=variant, style=style, negative_tags=SWALLOW_BOY_NEGATIVE)
