# AI Set Builder Intelligence — Design Spec

> The product is NOT a DJ controller. It is an AI-powered set building system where Claude Code + 50 MCP tools are the primary interface, and the panel is a listening/feedback companion.

## Vision

A DJ with 23,000 analyzed tracks tells Claude: "Build me a 90-minute peak-time acid set starting at 126 BPM." Claude analyzes the library, scores thousands of transition pairs, optimizes track order via GA, and delivers a production-ready set. The panel plays it back with auto-crossfade so the DJ can listen, give feedback (like/ban), and iterate.

**What makes this BETTER than djay Pro AI:**
- 47 audio features per track (vs djay's ~10)
- 6-component transition scoring formula (BPM + Harmonic + Energy + Spectral + Groove + Timbral)
- 12 transition recipe types with stem-level instructions
- 15 techno subgenre classifier (not just "electronic")
- 8 set templates with slot-based energy arcs
- GA optimizer tests millions of orderings (vs djay's sequential automix)
- Claude understands context: "like last time but darker" or "avoid tracks I banned in March"

## Problem

Current gaps that prevent best-possible sets:

1. **No transition memory** — every set builds from scratch, no learning from past transitions
2. **No track affinity** — "these 2 tracks sound amazing together" is never recorded
3. **Feedback is session-only** — like/ban data lost on reload
4. **Energy arc is template-rigid** — can't adapt mid-set based on vibe
5. **No set narrative** — Claude can't reason about "story" (tension/release/peak)
6. **Scoring is static** — same weights for all genres, no personalization

## Sub-projects (6 phases)

### Phase 1: Transition Memory (this spec)
Record every transition outcome. Use history to improve future scoring.

### Phase 2: Track Affinity Matrix
"These pairs work well together" based on transition history + user feedback.

### Phase 3: Persistent Feedback
Like/Ban/Rating stored in DB per track. Claude queries before building.

### Phase 4: Adaptive Energy Arc
Energy curve adjusts based on session feedback, not just template.

### Phase 5: Set Narrative Engine
Claude reasons about set "story" — intro/tension/peak/release/cooldown.

### Phase 6: Personal Scoring Weights
User preferences tune the 6-component formula (e.g., "I care more about groove than key").

---

## Phase 1: Transition Memory

### What

Every time the panel plays a crossfade (auto-DJ or manual "Mix Now"), log:
- From track ID + To track ID
- Transition score (6 components)
- Style used (cut/swap/harmonic/fade/echo_out/filter_sweep)
- Duration (bars, seconds)
- Tempo match ratio
- User reaction (if any): like, ban, skip, or listen-through

Store in new DB table `transition_history`. MCP tools read this to improve future `score_transitions` and `suggest_next_track`.

### DB Schema

```sql
CREATE TABLE transition_history (
    id SERIAL PRIMARY KEY,
    from_track_id INTEGER NOT NULL REFERENCES tracks(id),
    to_track_id INTEGER NOT NULL REFERENCES tracks(id),
    overall_score FLOAT,
    bpm_score FLOAT,
    harmonic_score FLOAT,
    energy_score FLOAT,
    spectral_score FLOAT,
    groove_score FLOAT,
    timbral_score FLOAT,
    style VARCHAR(30),
    duration_sec FLOAT,
    tempo_match_ratio FLOAT,
    user_reaction VARCHAR(20), -- 'like', 'ban', 'skip', 'listened', NULL
    session_id VARCHAR(64),    -- group transitions by listening session
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_track_id, to_track_id, session_id)
);

CREATE INDEX idx_transition_history_from ON transition_history(from_track_id);
CREATE INDEX idx_transition_history_to ON transition_history(to_track_id);
CREATE INDEX idx_transition_history_score ON transition_history(overall_score DESC);
```

### MCP Tools

| Tool | Params | Purpose |
|------|--------|---------|
| `log_transition` | from_id, to_id, score, components, style, duration, reaction | Record a completed transition |
| `get_transition_history` | from_id?, to_id?, limit, min_score? | Query past transitions |
| `get_best_pairs` | track_id, limit | Top-N best historical partners for a track |
| `update_reaction` | transition_id, reaction | Add user feedback to a transition |

### Integration with existing tools

**`score_transitions`** — after computing scores, check `transition_history`:
- If pair was played before with `reaction='like'` → boost score by 10%
- If pair was played before with `reaction='ban'` → hard reject (score=0)
- If pair was played before with `reaction='skip'` → penalize by 15%

**`suggest_next_track`** — prefer tracks that historically scored well:
- Query `get_best_pairs(current_track_id)` → merge with computed candidates
- Tracks with `listened` reaction (no explicit feedback = neutral) get slight boost

**`build_set`** — GA fitness function bonus for historically-good pairs:
- `fitness += history_bonus * count_of_liked_pairs_in_sequence`

### Panel changes

**`audio-player-context.tsx`** — already has `TransitionLog` interface with all needed fields. After each crossfade, the engine logs to console. Change: also call server action `logTransition()`.

**`actions/transition-log-actions.ts`** — new server action:
```typescript
export async function logTransition(log: TransitionLog): Promise<void> {
  await callTool('log_transition', {
    from_id: log.from.id,
    to_id: log.to.id,
    overall_score: log.overallScore,
    style: log.resolvedStyle,
    duration_sec: log.durationSec,
    tempo_match_ratio: log.tempoMatchRatio,
  })
}
```

**Like/Ban buttons** — already exist in `page.tsx`. Change: also call `update_reaction(transition_id, 'like'|'ban')`.

### Files to create/modify

| File | Action |
|------|--------|
| `app/db/models/transition_history.py` | NEW — SQLAlchemy model |
| `app/db/migrations/xxx_add_transition_history.py` | NEW — Alembic migration |
| `app/db/repositories/transition_history.py` | NEW — Repository |
| `app/services/transition_history.py` | NEW — Service |
| `app/controllers/tools/transition_history.py` | NEW — MCP tools |
| `app/schemas/transition_history.py` | NEW — Pydantic DTOs |
| `panel/actions/transition-log-actions.ts` | NEW — Server action |
| `panel/components/audio-player/audio-player-context.tsx` | MODIFY — call logTransition after crossfade |
| `app/services/set/scoring.py` | MODIFY — integrate history bonus |
| `app/controllers/tools/sets.py` (suggest_next_track) | MODIFY — query history |

### Success criteria

1. Every crossfade in panel auto-logs to `transition_history`
2. `get_best_pairs(track_id)` returns historically-liked pairs
3. `suggest_next_track` prefers historically-good transitions
4. Banned transitions never suggested again
5. After 50+ transitions logged, set quality measurably improves (higher avg score)

### Risks

1. **Cold start** — no history on first use. Mitigate: pure scoring works without history, history is a bonus.
2. **Feedback sparsity** — most transitions won't get explicit like/ban. Mitigate: "listened through without skipping" = implicit positive signal.
3. **Staleness** — old feedback may not reflect current taste. Mitigate: time-decay weight (recent feedback counts more).

---

## Future phases (not designed yet)

- Phase 2: Track Affinity Matrix — bidirectional pair scoring table
- Phase 3: Persistent Feedback — per-track rating (1-5), ban list, favorites
- Phase 4: Adaptive Energy Arc — session-reactive energy curve
- Phase 5: Set Narrative Engine — Claude reasons about set "story"
- Phase 6: Personal Scoring Weights — user-tuned formula coefficients
