# Declarative MCP — DJ Expert AI Design

> An AI using this MCP should think like a professional DJ. When a user says
> "dark and driving", the AI acts — it does not ask "what BPM range?".

---

## Problem

The current MCP is imperative: `build_set` accepts technical parameters and
returns a result. An AI using it must already know the right parameters. It
cannot hold a natural conversation, understand intent, or make professional
judgments autonomously.

The goal is to make the MCP self-sufficient: any AI that connects to it
immediately has the knowledge, vocabulary, and tools of an experienced DJ.

---

## Design

Three layers, each independently useful and testable.

---

### Layer 1 — Knowledge Resources

Four static JSON resources always available at `knowledge://`. No database
access required. The AI reads these at session start as a professional reads
a briefing document.

#### `knowledge://vocabulary`

Maps human descriptors to technical parameters. The AI translates intent
without asking the user to explain themselves.

| Human term | Subgenres | BPM | Key features |
|---|---|---|---|
| dark | detroit, industrial, raw | 128–140 | kick_prominence > 0.6, atonality |
| hard | peak_time, hard_techno, industrial | 134–145 | energy_mean > 0.7 |
| hypnotic | hypnotic, minimal, detroit | 128–135 | low spectral_flux_std, onset_rate 2–4 |
| acid | acid | 128–138 | centroid > 3000 Hz, high flux |
| melodic | melodic_deep, progressive | 126–134 | hp_ratio > 2.0, key_confidence > 0.7 |
| atmospheric | ambient_dub, dub_techno | 120–132 | energy_mean < 0.3 |
| driving | driving, tribal, peak_time | 130–140 | kick_prominence > 0.5, pulse_clarity |
| groovy | tribal, breakbeat | 128–136 | high onset_rate, syncopated kick |
| raw | raw, industrial | 132–145 | high crest_factor, distorted spectral |
| deep | dub_techno, minimal | 124–132 | low centroid, wide stereo, LRA > 10 LU |

The full vocabulary derives from `app/audio/classification/profiles.py`.
Implementer must extract all 15 subgenre feature profiles into this resource.

Time-of-night context:

| Time | Phase | Template |
|---|---|---|
| 23:00–01:00 | Warm-up | warm_up_30, classic_60 |
| 01:00–03:00 | Build | classic_60, roller_90 |
| 03:00–05:00 | Peak | peak_hour_60, roller_90 |
| 05:00+ | Closing | closing_60 |

#### `knowledge://subgenre-guide`

All 15 techno subgenres with cultural context, not just technical parameters.

Each entry includes:
- Human description (what it sounds like, cultural origin, typical artists)
- Technical signature (BPM, energy, spectral profile)
- Set position (warm-up / mid / peak / closing)
- Compatible neighbors (which subgenres mix naturally before and after)

Example entry for `detroit`:
```text
detroit — The birthplace. Mechanical, soulful, industrial undertones.
Think Underground Resistance, Jeff Mills. Mid-to-peak energy.
BPM 128–136. Mixes well after: melodic_deep, dub_techno.
Mixes well before: industrial, peak_time.
```

#### `knowledge://set-dynamics`

Theory of DJ set construction in plain language:

- **The 20-minute rule**: crowds need 20 minutes to warm up. Opening with
  peak energy empties the dancefloor.
- **Energy arc**: a set tells a story — tension builds, peaks, then
  resolves. Without resolution, the crowd feels exhausted, not satisfied.
- **Tension and release cycles**: every 20–30 minutes, introduce a
  breakdown or softer track. This resets attention and makes the next peak
  hit harder.
- **Hard rules**: never jump more than 2 energy levels between consecutive
  tracks; outro should land, not cliff-drop.
- **Phrase awareness**: techno tracks operate in 8- and 16-bar phrases.
  Transitions work best at phrase boundaries.

#### `knowledge://dancefloor-psychology`

How crowds respond and why:

- **Hands in the air**: bright lead synths, euphoric harmonic progressions,
  loud kick, LUFS -9 to -8
- **Nodding heads**: hypnotic loops, minimal variation, consistent groove,
  LUFS -12 to -11
- **Eyes closed, arms crossed**: dark atmosphere, low melodic content,
  industrial textures — the "serious" dancefloor state
- **Energy recovery**: after an intense peak, one softer track lets the
  crowd catch breath without losing them. Skip it and they leave.
- **Harmonic mixing perception**: out-of-key transitions sound "wrong"
  even to non-musicians. Camelot distance ≥ 5 is audible.

---

### Layer 2 — Session Initialization Prompt

**`dj_expert_session(goal?)`**

A multi-message prompt that boots the AI as a DJ expert. The AI calls it
once at session start, or it fires automatically when a user describes an
intent in natural language.

What the prompt does:

1. Reads `library://current-state` — actual library snapshot: which
   subgenres are represented, how many tracks per subgenre, average quality
   score, which playlists exist
2. Reads all four `knowledge://` resources
3. Issues behavioral instructions to the AI:
   - Translate human intent; do not ask for BPM ranges
   - Make reasonable assumptions; state them briefly
   - Ask questions only when intent is genuinely ambiguous
   - Speak like a DJ, not a database interface
4. Returns an opening message in the style of a professional assistant:
   *"I can hear you want something dark and driving for late night.
   I'll pull from detroit and industrial, 132–140 BPM, 60 minutes.
   One question: is this after midnight, or earlier in the evening?"*

The prompt is the bridge between user intent and autonomous action.

---

### Layer 3 — Atomic Tools

Two tools the current MCP does not have. Both give the AI fine-grained
control over the pipeline without locking it into `build_set`'s fixed path.

#### `get_candidate_pool`

```text
get_candidate_pool(
    description: str | None,      # "dark hypnotic tracks"
    subgenres: list[str] | None,  # ["detroit", "minimal"]
    bpm_min: float | None,
    bpm_max: float | None,
    energy_level: str | None,     # "low" | "mid" | "high"
    lufs_min: float | None,
    lufs_max: float | None,
    limit: int = 50,
) -> list[TrackSummary]
```

Returns tracks from the library matching the criteria. The AI explores
options before committing to a set. Does not create a set version, writes
nothing to the database.

This fills the gap between "search the library" and "build a full set".
The AI can sample the pool, check subgenre distribution, verify that
enough tracks exist, then proceed to build.

#### `preview_set_arc`

```text
preview_set_arc(
    track_ids: list[int],
    template: str | None,
) -> {
    score: float,
    energy_arc: list[float],   # LUFS per position
    bpm_arc: list[float],      # BPM per position
    weak_spots: list[int],     # positions with score < 0.5
    recommendation: str,       # plain-language summary
}
```

Runs the fitness function on a specific track list without saving a set
version. The AI can simulate multiple orderings, compare arc shapes, and
identify problems before committing.

This is the missing "what if" tool. Currently the only way to evaluate an
ordering is to build a full set and call `quick_set_review`. That creates
noise in the set history. `preview_set_arc` is non-destructive.

---

## Data Flow

```text
User: "dark and driving, late night, 90 minutes"
        ↓
dj_expert_session() reads:
  library://current-state   → "detroit: 11 tracks, industrial: 3 tracks"
  knowledge://vocabulary    → dark = detroit/industrial, driving = peak_time
  knowledge://set-dynamics  → late night → peak phase, roller_90 template
        ↓
AI (no questions asked):
  get_candidate_pool(subgenres=["detroit","industrial","peak_time"], bpm_min=130, limit=60)
        ↓
  preview_set_arc(candidate_ids, template="roller_90")
  → score 0.79, weak spot at position 12
        ↓
  rebuild_set with adjusted candidates
        ↓
"Here's your 90-minute dark roller. 14 tracks, 130–140 BPM.
 Weak link between tracks 12 and 13 — different feel. Want me to swap?"
```

---

## What Does Not Change

- All existing tools remain untouched (`build_set`, `audit_playlist`, etc.)
- Existing workflow prompts remain
- Database schema unchanged
- No breaking changes to current MCP clients

---

## Files to Create or Modify

| File | Action | Responsibility |
|---|---|---|
| `app/controllers/resources/knowledge.py` | Create | All four `knowledge://` resources |
| `app/controllers/prompts/workflows/dj_expert_session.py` | Create | Session initialization prompt |
| `app/controllers/tools/candidate_pool.py` | Create | `get_candidate_pool` tool |
| `app/optimization/preview.py` | Create | Pure `preview_set_arc` logic |
| `app/controllers/tools/sets.py` | Modify | Add `preview_set_arc` tool |

---

## Success Criteria

1. An AI with no prior instructions can receive *"something dark and late
   night"* and produce a playable set without asking technical questions
2. Knowledge resources contain enough cultural depth that the AI can
   explain its choices in plain language
3. `get_candidate_pool` + `preview_set_arc` together replace the need to
   call `build_set` speculatively just to evaluate options
4. Existing tools and tests pass without modification
