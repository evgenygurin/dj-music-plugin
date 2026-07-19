# RimJoba Suno Voice Recipe — Design Spec

Date: 2026-07-18
Status: approved (design phase)
Scope: prompt-only recipe (no Persona/Voice create)

## Purpose

Зафиксировать **уникальный переиспользуемый голос RimJoba** в Suno через
жёсткий vocal-lock промпт-рецепт (подход A), без создания Persona/Voice в API.

Референс тембра и delivery:

- Suno song: https://suno.com/song/e4d68e9a-d35d-4e70-8af0-4205cf484d2f
- Title: «Графский Самовар» (persona root «Тaras»)
- Clip id: `e4d68e9a-d35d-4e70-8af0-4205cf484d2f`
- Observed style DNA: Russian trap / drill-tinged hip-hop ~140 BPM, half-time
  bounce, **deadpan delivery, cold cocky, light autotune, wide ad-libs,
  gang-chant hook**, clean raw mix

## Context (research snapshot)

### Library state (Suno account `sberpunk`, 2026-07-18)

- Existing personas: Milash, Patap, Sber Hypno (legacy), барский пирожок,
  Тaras, My Voice — **нет persona «RimJoba»**.
- Fresh RimJoba batch (chirp-fenix / v5.5): 10 titles × 2 variants each
  (Легенда, Танцпол, После полуночи, Пульт и микрофон, Сто сорок, Над городом,
  Подвал, Ночь не спит, Все дороги, Высшая проба).
- Problem: genre chameleon + inconsistent vocal negatives (`no autotune` /
  `no singing` on many takes) → voice drift across tracks.
- Older local assets in `suno_out/` («Просто повезло» family): low baritone
  pocket (~80–130 Hz F0 on dark takes); useful for mood, **not** the locked
  signature (user locked to Taras reference).

### Official Suno guidance used

- Personas = song essence (vocals + style + vibe) reusable across gens
  (Suno blog «Introducing Personas»).
- Voices (v5.5) = verified personal vocal; quiet room; practice; longer ref
  (≥60s ideal); match genre; Audio Influence high when voice drifts
  (Suno blog «6 tips for Voices» + help «Voices» / FAQ).
- Style Persona create needs completed root clip + description; vocal window
  10–30s on sunoapi path. **Out of scope for this spec** (prompt-only).

### Approach chosen

| Option | Summary | Decision |
|--------|---------|----------|
| A. Hard vocal-lock | One immutable VOICE BLOCK + genre tail | **Selected** |
| B. Core + 3 modes | street / club / late-night delivery variants | Deferred |
| C. Cover/Persona-first | Create persona from Taras root | Out of scope (no create) |

## Goals

1. One copy-paste **VOICE BLOCK** that forces Taras-like RimJoba vocal identity.
2. Swappable **GENRE TAIL** that never overrides vocal descriptors.
3. Fixed **NEGATIVE** anti-drift list.
4. Lyrics performance rules (ad-libs, deadpan tags, name placement).
5. Repeatable workflow for Custom Mode gens on v5 / v5.5.

## Non-goals

- Creating Suno Persona or Voice via API/UI.
- Cloning a real human without rights (recipe is fictional MC identity).
- Changing plugin code / MCP tools (docs-only deliverable).
- Importing generated files as library `audio_file` tracks.

## Success criteria

Generate ≥3 tracks in different genres (trap, techno-rap, boom-bap) with the
**same VOICE BLOCK**. Pass if a blind listen identifies one MC (deadpan cold
cocky, light AT, wide ad-libs, gang hooks) rather than three different singers.

## Recipe contract

| Field | Rule |
|-------|------|
| VOICE BLOCK | Immutable; ~40–60% of style budget; always first |
| GENRE TAIL | Per-track; instruments/BPM/groove only; no vocal words |
| NEGATIVE | Always on; optional genre-neg append |
| Lyrics | Performance tags + Taras-style ad-libs |
| Model | v5 / v5.5 (`chirp-fenix` / `chirp-crow` class) |
| Persona/Voice create | Out of scope |

---

## Copy-paste blocks

### 1. VOICE BLOCK (never edit between tracks)

```text
RimJoba signature male voice: mid-baritone Russian rap MC, deadpan delivery, cold cocky swagger, close-mic dry presence, light autotune (subtle, not melodic robot), wide stereo ad-libs, gang-chant hooks, short delay throws on key lines, punchy consonants, relaxed jaw, half-time pocket feel even at double-time bursts, clean raw mix, intimate and arrogant at once
```

Locks (from Taras reference):

- deadpan + cold cocky
- light autotune (explicitly **not** `no autotune`)
- wide ad-libs + gang-chant hooks
- close-mic, punchy, clean raw
- swagger without hysteria

Must **not** include: genre names, BPM, 808/cowbell/orchestra (those go in tail).

### 2. GENRE TAIL catalog

Append after VOICE BLOCK as: `{VOICE BLOCK}. {GENRE TAIL}.`

| Mode | GENRE TAIL |
|------|------------|
| street trap | `Russian trap, drill-tinged hip-hop, 140 BPM, half-time bounce, booming distorted 808, punchy trap kick, triplet hi-hats, sparse dark bells, detuned synth melody, trap risers` |
| techno-rap | `techno-rap, 140 BPM four-on-the-floor warehouse rave, cold synth pulse, syncopated kick-bass, sparse drums in verses, club delay throws` |
| boom-bap | `boom-bap hip-hop, dusty breakbeats, swung drums, vinyl scratches, head-nod groove, sparse bass-kick-snare pocket` |
| phonk | `phonk, dusty Memphis bounce, chopped cowbell groove, hard sub pulses, tape wobble, smoky half-time pocket` |
| club | `Russian club-pop anthem, four-on-the-floor kick, buoyant synth stabs, chantable crowd hooks, filtered build, handclap outro` |
| late-night* | `jazz-hop, laid-back swung pocket, dusty brushes, upright bass, muted keys, soft sax answers, warm Rhodes` |

\*late-night still keeps VOICE BLOCK (deadpan cocky). Do not replace with
«breathy crooner» language.

### 3. NEGATIVE (always)

```text
female vocals, choir lead, ethereal singer, opera, melodic crooner, heavy melisma, robotic extreme autotune, chipmunk, kids voice, whisper-only ASMR, folk, accordion, balalaika, orchestral lead vocal
```

Optional genre-neg append examples:

- trap: `acoustic guitar ballad, ukulele`
- phonk: `bright EDM festival drop, happy hardstyle`
- boom-bap: `hyperpop, nightcore`
- club: `funeral dirge, ambient drone only`

### 4. Full style assembly example

```text
RimJoba signature male voice: mid-baritone Russian rap MC, deadpan delivery, cold cocky swagger, close-mic dry presence, light autotune (subtle, not melodic robot), wide stereo ad-libs, gang-chant hooks, short delay throws on key lines, punchy consonants, relaxed jaw, half-time pocket feel even at double-time bursts, clean raw mix, intimate and arrogant at once. Russian trap, drill-tinged hip-hop, 140 BPM, half-time bounce, booming distorted 808, punchy trap kick, triplet hi-hats, sparse dark bells, detuned synth melody, trap risers.
```

Negative:

```text
female vocals, choir lead, ethereal singer, opera, melodic crooner, heavy melisma, robotic extreme autotune, chipmunk, kids voice, whisper-only ASMR, folk, accordion, balalaika, orchestral lead vocal
```

---

## Lyrics performance rules

1. **Section tags** at verse start: `[deadpan, low, close mic]`  
   Hook: `[cold cocky, gang doubles]`  
   Optional burst: `[double-time burst]` for 4–8 bars max.
2. **Ad-libs** at line ends (Taras pattern): `(е) (а) (ха) (скр) (бра) (эй)`.
3. **Hook law**: one memetic anchor line 3–6 words, repeated; verses serve the hook.
4. **Name placement**: `Римджо́ба` / `RimJoba` once in intro + once in hook —
   not every bar.
5. **No melodic crooner bridges**; if sung hook needed, keep it chant-like,
   not pop ballad melisma.
6. **Language**: Russian primary; translit only when intentionally mangling
   (avoid accidental genre-bleed like bare `Kazakh Pop` tokens inside lyrics).

### Minimal lyrics skeleton

```text
[Intro]
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
```

---

## Workflow (Custom Mode, no create)

1. Paste **VOICE BLOCK** into style (first).
2. Append one **GENRE TAIL**.
3. Paste **NEGATIVE**.
4. Paste lyrics with performance tags + ad-libs.
5. Title: `RimJoba — <track name>`.
6. Model: v5 or v5.5; male vocal if UI exposes gender.
7. Generate (2 variants).
8. Keep only takes that match Taras DNA (deadpan, light AT, wide ad-libs).
9. If drift: raise Audio Influence (if Voice/ref available later); **do not**
   edit VOICE BLOCK — only change GENRE TAIL or lyrics density.
10. Reject takes that introduce choir-lead, heavy melisma, or female lead.

### Anti-patterns (do not)

- Putting `no autotune` / `no singing` in negative or tags (breaks Taras lock).
- Putting vocal adjectives only in GENRE TAIL and omitting VOICE BLOCK.
- Genre words inside lyrics that Suno promotes into style (e.g. raw
  `Afrobeats` / `Q-Pop` tokens mid-verse without musical need).
- Stacking multiple conflicting vocal personas («ethereal choir + gritty male»).
- Rewriting VOICE BLOCK per mood («warm wise» vs «cold cocky»).

---

## Future (out of scope now)

When user allows create:

1. Pick best RimJoba take that already matches this recipe (or cover from
   Taras root `e4d68e9a-…`).
2. Create Style Persona `RimJoba` with description = VOICE BLOCK + primary
   street-trap tail; vocal window on densest 15–25s of lead vocal.
3. Optional: Suno Voice from clean acapella if personal vocal rights exist
   (verify phrase, quiet room, ≥60s, Audio Influence high, v5.5 only).
4. Store `persona_id` in project notes / future config — still keep this
   recipe as fallback for session-mode gens without persona field.

## Verification checklist

- [ ] Style always starts with full VOICE BLOCK verbatim
- [ ] GENRE TAIL has zero vocal-identity words
- [ ] NEGATIVE includes female/choir/crooner/extreme-AT bans
- [ ] Lyrics use deadpan tags + (е/а/ха/скр/бра) ad-libs
- [ ] Blind A/B vs Taras reference: same MC swagger
- [ ] Three-genre test passes (trap / techno-rap / boom-bap)

## Deliverable

This document only. No code, no Suno write calls, no persona create.
