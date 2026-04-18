# Phase 2: Track Affinity Matrix — Design Spec

## Goal

Build a bidirectional pair scoring table from transition_history data. When Claude builds a set, it knows which track pairs have proven chemistry — not just computed scores, but real-world outcomes.

## How it works

1. Aggregate `transition_history` into `track_affinity` table
2. Each row = one ordered pair (A→B) with: play_count, avg_score, like_count, ban_count, net_sentiment
3. `score_transitions` reads affinity to boost/penalize pairs
4. `suggest_next_track` merges affinity data with computed candidates
5. `build_set` GA fitness includes affinity bonus

## DB Schema

```sql
CREATE TABLE track_affinity (
    id SERIAL PRIMARY KEY,
    track_a_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    track_b_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    play_count INTEGER DEFAULT 0,
    avg_score FLOAT,
    like_count INTEGER DEFAULT 0,
    ban_count INTEGER DEFAULT 0,
    skip_count INTEGER DEFAULT 0,
    net_sentiment FLOAT DEFAULT 0,  -- (likes - bans - 0.5*skips) / play_count
    last_played_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(track_a_id, track_b_id)
);
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `refresh_affinity` | Rebuild affinity from transition_history (batch) |
| `get_track_affinity` | Get affinity data for a pair or all pairs for a track |
| `get_affinity_recommendations` | Top-N tracks with best affinity for a given track |

## Integration

- `score_transitions`: `overall_quality += affinity.net_sentiment * 0.1`
- `suggest_next_track`: merge affinity top-N with computed candidates
- `build_set` GA: fitness bonus for high-affinity consecutive pairs

## Files

| File | Action |
|------|--------|
| `app/db/models/track_affinity.py` | NEW |
| `app/db/repositories/track_affinity.py` | NEW |
| `app/services/track_affinity.py` | NEW |
| `app/schemas/track_affinity.py` | NEW |
| `app/controllers/tools/track_affinity.py` | NEW |
| `app/controllers/dependencies/repos.py` | MODIFY |
| `app/controllers/dependencies/services.py` | MODIFY |
