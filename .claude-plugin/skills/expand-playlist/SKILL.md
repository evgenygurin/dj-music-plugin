---
name: expand-playlist
description: Use when expanding a techno subgenre playlist (minimal, acid, dub, etc.) using the snowball method — per-track YM recommendations + L1+L2 quality gate.
---

# Expanding a Techno Subgenre Playlist (Snowball Method)

## Core Idea

Each track in the playlist is a seed. For every seed we fetch K YM recommendations,
run L1+L2 analysis on candidates, and add only tracks that match the target subgenre.
Newly added tracks become seeds for the next round — the playlist grows like a snowball.

```text
Round 1: [seed1, seed2, ..., seedN]
          ↓ recs_per_track=3
         [cand1..cand3N]
          ↓ classify_mood (L1+L2)
          ↓ mood == target AND confidence >= min_confidence
         [new1, new2, ...]  ← added to playlist

Round 2: [seed1..seedN, new1, new2, ...]
          ↓ same process
         [more new tracks]

Repeat until target_count reached or rounds exhausted.
```

### Why per-track (not per-playlist) recommendations?

YM recommendations for a playlist are generic. Recommendations for a specific
minimal techno track are tightly focused — YM's model knows that track's context.
Iterating track-by-track gives richer, more relevant candidates.

---

## Parameters

| Parameter | Default | Purpose |
|---|---|---|
| `recs_per_track` | 3 | YM recommendations to fetch per track per round |
| `rounds` | 3 | Snowball iterations |
| `min_confidence` | 0.3 | Minimum `mood_confidence` to accept a candidate |
| `target_mood` | (playlist subgenre) | Subgenre to match (e.g., `minimal`, `acid`) |
| `target_count` | 50 | Stop early when playlist reaches this size |

---

## Step 1 — Seed the Playlist

The playlist **must have seed tracks before starting**. Seeds define the sound.
With no seeds the YM recommendations have no context and return generic results.

**Minimum: 5–10 representative tracks of the target subgenre.**

### Option A: Import from YM search

```text
# Find known artists of the subgenre
ym_search(query="Richie Hawtin minimal techno", type="tracks", limit=5)
ym_search(query="Magda techno minimal", type="tracks", limit=5)
ym_search(query="Ricardo Villalobos minimal", type="tracks", limit=5)

# Import metadata only (no audio yet)
import_tracks(
  track_refs=["ym:111", "ym:222", ...],
  playlist_id=<target_playlist_id>,
  auto_analyze=false
)
```

### Option B: Use tracks already in library

```text
filter_tracks(mood="minimal", limit=10)
manage_playlist(action="add_tracks", data={id: <playlist_id>}, track_refs=[...])
```

---

## Step 2 — Classify Seeds (L1+L2)

Seeds need features so their recommendations are meaningful and so they act as
a quality baseline. Skip if seeds already have `mood` classified.

```text
classify_mood(playlist_id=<playlist_id>, reclassify=false)
```

- ~5 sec/track, 6 parallel threads
- Persists `mood` and `mood_confidence` to DB

Check results:

```text
audit_playlist(playlist_id=<playlist_id>, check="techno_quality")
```

Remove seeds with `mood_confidence < 0.3` or wrong subgenre — bad seeds pollute recommendations.

---

## Step 3 — Snowball Expansion (main loop)

Run this loop `rounds` times or until `target_count` is reached.

### 3a — Get recommendations per track

```text
# For each track_id in playlist:
find_similar_tracks(
  track_id=<track_id>,
  strategy="ym_recommendations",
  limit=<recs_per_track>   # default 3
)
```

Collect unique candidate YM IDs not already in the playlist.

### 3b — Import candidates (metadata only)

```text
import_tracks(
  track_refs=["ym:<id1>", "ym:<id2>", ...],
  auto_analyze=false
)
```

No audio downloaded yet — we only need metadata + L1+L2 features.

### 3c — Run L1+L2 quality gate

```text
classify_mood(track_ids=[<candidate_id1>, <candidate_id2>, ...], reclassify=false)
```

### 3d — Filter and add passing tracks

Keep candidates where:
- `mood == target_mood`
- `mood_confidence >= min_confidence`

```text
manage_playlist(
  action="add_tracks",
  data={id: <playlist_id>},
  track_refs=["local:<passing_id1>", ...]
)
```

Discard (or archive) candidates that failed the quality gate.

### 3e — Repeat

The just-added tracks are now seeds for the next round. Go to 3a.

---

## Step 4 — Final Audit

```text
audit_playlist(playlist_id=<playlist_id>)
```

Check distribution of moods and remove outliers if needed.

---

## Step 5 — Distribute to Subgenre Playlists (optional)

If you want to split results across 15 subgenre playlists:

```text
distribute_to_subgenres(source_playlist_id=<playlist_id>, dry_run=true)
distribute_to_subgenres(source_playlist_id=<playlist_id>, sync_to_ym=true)
```

---

## Step 6 — Sync to YM (optional)

```text
sync_playlist(playlist_id=<playlist_id>, direction="push", dry_run=true)
sync_playlist(playlist_id=<playlist_id>, direction="push")
```

albumId is resolved automatically — pass bare YM track IDs.

---

## Minimal Subgenre Discriminators

Features used by `classify_mood` to identify `minimal`:

| Feature | Minimal range | Notes |
|---|---|---|
| `kick_prominence` | 0.05 – 0.2 | Low — sparse percussion |
| `hp_ratio` | 2.0 – 6.0 | Harmonic > percussive |
| `spectral_centroid` | 400 – 1000 Hz | Mid-low register |
| `energy_mean` | 0.15 – 0.35 | Calmer than peak_time |
| `bpm` | 120 – 130 | Slower end of techno range |

**Common confusion:** minimal ↔ dub_techno (both high HP ratio).
Dub tends to have wider `loudness_range_lu` and lower `spectral_flux_std`.

---

## Performance Reference

| Phase | Tracks | Time (parallel) |
|---|---|---|
| import_tracks (metadata only) | any | < 1s |
| classify_mood L1+L2 | 50 candidates | ~1.5 min |
| find_similar_tracks per track | 20 seeds × 3 recs | ~30 sec (YM rate limit) |
| 1 full round (20 seeds) | 60 candidates | ~2 min |
| 3 rounds | ~180 candidates checked | ~6 min |

---

## Gotchas

- `find_similar_tracks` with `strategy="ym_recommendations"` uses YM API — subject to rate limiting
- Candidates already in the playlist are skipped automatically by `import_tracks` (dedup by YM ID)
- `import_tracks` without `auto_analyze=true` skips audio — run `classify_mood` explicitly after
- `classify_mood` L1+L2 downloads a 30s clip, analyzes, deletes — no permanent MP3 stored
- `distribute_to_subgenres` creates YM playlists if they don't exist — confirm with `dry_run=true` first
- After `sync_playlist`, always re-fetch to get fresh revision before next modification
- Bad seeds (wrong mood/confidence) will generate off-genre recommendations — clean seeds before expanding
