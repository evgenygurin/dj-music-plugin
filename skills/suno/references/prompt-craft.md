# Suno Prompt Craft Reference

## Field Split

- Custom vocal: `prompt` = exact lyrics; style/tags = genre, voice, BPM/key, arrangement, production; negative tags = exclusions.
- Custom instrumental: `instrumental=true`; style/tags carry the whole brief; keep prompt non-empty in web mode.
- Simple/non-custom: `prompt` is a short idea; lyrics may be generated and may not match exactly.

## Structure Tags

Use concise tags: `[Intro]`, `[Verse]`, `[Pre-Chorus]`, `[Hook]`, `[Chorus]`, `[Bridge]`, `[Build]`, `[Drop]`, `[Breakdown]`, `[Outro]`.

Use vocal cues sparingly: `[deadpan, low, close mic]`, `[controlled, dry]`, `[light autotune, restrained]`, `(эй)`, `(ха)`, `(скр)`.

## DJ Asset Pattern

Style template:

`<subgenre> DJ tool, <BPM> BPM, Camelot <key>, <8/16/32>-bar loop, loopable phrasing, clean downbeat, no vocal, no lead hook, no long intro, no long outro, mixable low-end, <texture>`

Examples:

- Gap fill: `deep dub techno texture bed, 124 BPM, Camelot 8A, 16 bars, low RMS movement, no kick takeover, no vocal`.
- Bridge: `hypnotic techno bridge loop, 126 BPM, Camelot-compatible 7A/8A, 32 bars, rolling 909, muted stabs, clean intro/outro handles`.
- Rescue loop: `peak-time techno emergency transition tool, 132 BPM, 16 bars, strong downbeat, tight kick-bass, no vocal, no breakdown`.

## Voice Lock

- Keep the same voice block across variants.
- Change only genre tail, BPM, and arrangement.
- Do not add contradictory negatives like `no autotune` when the recipe requires light autotune.
- For formal Suno Voice, use only the user's own voice and set `personaModel=voice_persona` with V5/V5_5.
