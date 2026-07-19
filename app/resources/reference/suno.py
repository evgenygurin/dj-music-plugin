"""Suno model, prompt-craft, and voice reference resources.

URIs:
- ``reference://suno/models``
- ``reference://suno/prompt-craft``
- ``reference://suno/voices``
"""

from __future__ import annotations

from fastmcp.resources import resource

from app.domain.suno_voice import (
    GENRE_TAILS,
    LYRICS_SKELETON,
    NEGATIVE_TAGS,
    REFERENCE_CLIP_ID,
    REFERENCE_URL,
    SWALLOW_BOY_NEGATIVE,
    SWALLOW_BOY_REFERENCE_CLIP_ID,
    SWALLOW_BOY_REFERENCE_URL,
    SWALLOW_BOY_VARIANTS,
    SWALLOW_BOY_VOICE_CORE,
    TARAS_ALBUM_TITLE,
    TARAS_ALBUM_TRACKS,
    TARAS_NEGATIVE,
    TARAS_VOICE_CORE,
    VOICE_BLOCK,
)
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META, json_dump

_MODELS_JSON = json_dump(
    {
        "updated_at": "2026-07-19",
        "sources": [
            "https://docs.sunoapi.org/llms.txt",
            "https://docs.sunoapi.org/suno-api/generate-music.md",
            ".claude/rules/suno.md",
        ],
        "defaults": {
            "session_web": "chirp-auk-turbo",
            "session_web_note": (
                "chirp-auk-turbo is a v4.5-turbo variant; the CURRENT Suno free "
                "default is v4.5-all (replaced the free model 2025-10-21). Always "
                "send a model the account's usable_models includes."
            ),
            "sunoapi_general": "V5",
            "sunoapi_voice": "V5_5",
            "sunoapi_compatibility": "V4_5",
        },
        "codename_map": {
            "note": "Suno bird codename -> version (help.suno.com / unifically.com, 3-0 verified 2026-07-19)",
            "chirp-fenix": "v5.5 (current stable, 2026-03-26; paid)",
            "chirp-crow": "v5.0 (paid)",
            "chirp-bluejay": "v4.5+ / V4_5PLUS (paid)",
            "chirp-auk": "v4.5 / V4_5 (paid)",
            "v4.5-all": "free plan default / V4_5ALL (since 2025-10-21)",
            "chirp-v4": "v4 (legacy)",
            "chirp-v3-5": "v3.5 (legacy)",
        },
        "free_vs_paid": {
            "free": "v4.5-all only; personal / non-commercial use",
            "paid": "v5, v5.5 and full line; commercial rights granted",
            "gotcha": "paid model key or empty mv on a free account -> 403",
        },
        "session_web": [
            {
                "model": "chirp-auk-turbo",
                "use": "project default for browser-session mode (v4.5-turbo variant; current free model is v4.5-all)",
                "confidence": "project-live-contract",
            },
            {
                "model": "chirp-fenix",
                "use": "v5.5-like paid/pro web key; verify account models first",
                "confidence": "project-live-contract-version-dependent",
            },
            {
                "model": "chirp-crow",
                "use": "v5-like paid/pro web key; verify account models first",
                "confidence": "project-live-contract-version-dependent",
            },
            {
                "model": "chirp-auk / bluejay",
                "use": "v4.5-like paid/pro web keys; verify account models first",
                "confidence": "project-live-contract-version-dependent",
            },
        ],
        "sunoapi": [
            {
                "model": "V4",
                "max_duration": "up to 4 minutes",
                "notes": "shorter prompt/style limits; refined structure/audio quality",
            },
            {
                "model": "V4_5",
                "max_duration": "up to 8 minutes",
                "notes": "smarter prompts, genre blending, faster output",
            },
            {
                "model": "V4_5PLUS",
                "max_duration": "up to 8 minutes",
                "notes": "richer sound and broader creative range",
            },
            {
                "model": "V4_5ALL",
                "max_duration": "up to 8 minutes",
                "notes": "better song structure; upload-extend has a 1-minute upload limit",
            },
            {
                "model": "V5",
                "max_duration": "current docs do not state a separate max beyond family limits",
                "notes": "current higher-quality/faster musical expression model",
            },
            {
                "model": "V5_5",
                "max_duration": "current docs do not state a separate max beyond family limits",
                "notes": "current voice/custom-model oriented model; supports voice_persona",
            },
        ],
        "pricing": {
            "note": "version-dependent; re-verify before relying (reported 2026-07-19)",
            "suno_free": "~50 credits/day; personal / non-commercial only",
            "suno_pro": "$10/mo -> 2,500 credits/mo; commercial rights; 0% revenue share",
            "suno_premier": "$30/mo -> 10,000 credits/mo; + Suno Studio",
            "sunoapi_org": "~$0.06/song (gateway; varies by provider)",
            "variants_per_generation": 2,
        },
        "operational_rules": [
            "Read provider account/models before choosing a paid web key.",
            "Session mode polls clip ids; sunoapi mode polls task ids.",
            "Always send an explicit non-empty prompt/model in web mode.",
            "Use V5/V5_5 for Suno Voice persona flows when available.",
        ],
    }
)


_PROMPT_CRAFT_JSON = json_dump(
    {
        "updated_at": "2026-07-19",
        "core_split": {
            "custom_vocal": "prompt is exact lyrics; style carries genre, voice, arrangement, BPM/key, mix notes",
            "custom_instrumental": "instrumental=true; style carries the complete brief; prompt may be minimal",
            "simple_mode": "prompt is a short idea; generated lyrics may not match exactly",
            "negative_tags": "exclude voices, genres, instruments, long intros, or unwanted production traits",
            "instrumental_caveat": "for instrumental output put [Instrumental] in the LYRICS field (the instrumental=true flag maps to this) — without it Suno adds vocals regardless of the style field",
        },
        "style_field": {
            "front_loading": "V5.5 tokenizer weights leading tokens more heavily; order genre -> timbre -> mood -> technical (BPM/key)",
            "tag_count": "8-15 tags is the sweet spot; >20 dilutes, <5 is too vague",
            "bpm_key_markers": "add explicit [BPM] 128 [Key] A minor markers to stabilize tempo/mood across regenerations",
        },
        "structure_tags": [
            "[Intro]",
            "[Verse]",
            "[Pre-Chorus]",
            "[Hook]",
            "[Chorus]",
            "[Bridge]",
            "[Build]",
            "[Drop]",
            "[Breakdown]",
            "[Outro]",
        ],
        "performance_cues": [
            "[deadpan, low, close mic]",
            "[controlled, dry]",
            "[light autotune, restrained]",
            "(эй)",
            "(ха)",
            "(скр)",
        ],
        "sliders": {
            "styleWeight": "0.00-1.00; higher follows style more strictly",
            "weirdnessConstraint": "0.00-1.00; higher allows more novelty/deviation",
            "audioWeight": "0.00-1.00; input-audio influence for upload/cover/extend flows",
        },
        "dj_asset_recipe": {
            "default": "instrumental, loopable, 8/16/32 bars, explicit BPM/key, no vocal, no lead hook",
            "gap_fill": "quiet bed, matched BPM/key, low novelty, no melodic takeover",
            "texture": "ambient/dub layer under original track, conservative drums",
            "bridge": "compatible Camelot key, energy between neighbouring tracks, clean mix handles",
            "rescue_loop": "short emergency transition loop, strong downbeat, no long intro/outro",
            "example_style": "hypnotic dub techno DJ tool, 126 BPM, Camelot 8A, 16-bar loop, deep rolling kick, muted dub chord stabs, tape echo, no vocal, no lead melody, clean intro/outro handles",
        },
        "guardrails": [
            "Do not over-specify every bar; keep the brief musical and readable.",
            "Use negative tags to remove broad unwanted traits, not to fight the whole prompt.",
            "For voice-lock, keep the same voice block across variants and change only the genre tail.",
            "For external audio, use sunoapi upload flows rather than web upload automation.",
        ],
    }
)


_VOICES_JSON = json_dump(
    {
        "updated_at": "2026-07-19",
        "voices": [
            {
                "id": "rimjoba",
                "kind": "prompt_only_voice_block",
                "reference_clip_id": REFERENCE_CLIP_ID,
                "reference_url": REFERENCE_URL,
                "voice_block": VOICE_BLOCK,
                "negative_tags": NEGATIVE_TAGS,
                "modes": sorted(GENRE_TAILS),
                "lyrics_skeleton": LYRICS_SKELETON,
                "cli": "uv run python scripts/rimjoba_prompt.py <mode> --title '<title>'",
                "cautions": [
                    "Do not create Persona/Voice unless explicitly requested.",
                    "Keep the full voice block unchanged; vary only the genre tail.",
                ],
            },
            {
                "id": "swallow_boy",
                "kind": "variant_ladder",
                "reference_clip_id": SWALLOW_BOY_REFERENCE_CLIP_ID,
                "reference_url": SWALLOW_BOY_REFERENCE_URL,
                "voice_block": SWALLOW_BOY_VOICE_CORE,
                "negative_tags": SWALLOW_BOY_NEGATIVE,
                "variants": [
                    {
                        "id": variant.variant_id,
                        "title_hint": variant.title_hint,
                        "twist": variant.twist,
                        "genre_tail": variant.genre_tail,
                    }
                    for variant in SWALLOW_BOY_VARIANTS
                ],
                "cli": "uv run python scripts/swallow_boy_variants.py",
                "cautions": [
                    "Use short clips and fast vocal entry for ladder tests.",
                    "Keep dry close-mic baritone traits stable across variants.",
                ],
            },
            {
                "id": "taras_album",
                "kind": "multiform_album_trackbook",
                "album_title": TARAS_ALBUM_TITLE,
                "voice_block": TARAS_VOICE_CORE,
                "negative_tags": TARAS_NEGATIVE,
                "tracks": [
                    {
                        "slug": track.slug,
                        "title": track.title,
                        "twist": track.twist,
                        "genre_tail": track.genre_tail,
                    }
                    for track in TARAS_ALBUM_TRACKS
                ],
                "cli": "uv run python scripts/taras_multiform_album.py",
                "cautions": [
                    "Use the trackbook as style/voice guidance, not as proof of rights.",
                    "Keep Taras voice core stable; change track mode and genre tail only.",
                ],
            },
        ],
        "formal_suno_voice": {
            "availability": "sunoapi mode only in this project surface",
            "workflow": [
                "voice.validate -> read validation phrase",
                "record exact phrase in user's own singing voice",
                "voice.generate with verifyUrl",
                "read voice record/check availability",
                "use personaId=<voiceId>, personaModel=voice_persona with V5/V5_5",
            ],
            "terms_guardrail": "Only create a voice model resembling the user's own voice.",
        },
    }
)


@resource(
    "reference://suno/models",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:suno"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def reference_suno_models() -> str:
    """Suno web/session and SunoAPI model defaults, limits, and caveats."""
    return _MODELS_JSON


@resource(
    "reference://suno/prompt-craft",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:suno"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def reference_suno_prompt_craft() -> str:
    """Prompt engineering rules for Suno generation and DJ utility assets."""
    return _PROMPT_CRAFT_JSON


@resource(
    "reference://suno/voices",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:suno"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def reference_suno_voices() -> str:
    """Project Suno voice recipes and formal Suno Voice workflow notes."""
    return _VOICES_JSON
