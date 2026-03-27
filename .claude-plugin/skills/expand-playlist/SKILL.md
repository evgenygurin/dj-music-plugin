---
name: expand-playlist
description: Use when expanding a techno subgenre playlist (minimal, acid, dub, etc.) using the snowball method — per-track YM recommendations + L1+L2 quality gate.
---

# Expanding a Techno Subgenre Playlist (Snowball Method)

## Core Idea

Process tracks **one at a time**. For each seed: get K recommendations → immediately
classify each candidate → immediately add passing ones to playlist and sync to YM →
move to next track. Newly added tracks become seeds for the next round.

**Do NOT batch recommendations from all tracks first.** Process and commit after each seed.

```text
for seed in playlist:
    recs = find_similar_tracks(seed, limit=K)          # 3 candidates
    for each rec:
        import_tracks([rec])                            # metadata only
        classify_mood([rec])                            # L1+L2 ~5s
        if mood == target AND confidence >= threshold:
            manage_playlist(add_tracks, [rec])          # add locally
            sync_playlist(direction="push")             # sync to YM now
    # move on to next seed (including just-added tracks)
```

### Why immediate add + sync (not batching)?

- Playlist stays consistent in YM throughout the process — stops are clean
- Newly added tracks are visible in YM immediately, useful during long runs
- Avoids large batch syncs that can hit YM rate limits
- If the process is interrupted, progress is not lost

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

**Process one seed at a time.** For each track in the playlist (including newly added ones),
run the sequence below before moving to the next track.

Stop when `target_count` is reached or all seeds in the current round are exhausted.

### 3a — Get recommendations for this track

```text
find_similar_tracks(
  track_id=<current_seed_id>,
  strategy="ym_recommendations",
  limit=<recs_per_track>   # default 3
)
```

Skip any returned IDs already present in the playlist.

### 3b — Import this candidate (metadata only)

```text
# Do this for each candidate individually, not all at once
import_tracks(
  track_refs=["ym:<candidate_id>"],
  auto_analyze=false
)
```

### 3c — L1+L2 quality gate for this candidate

```text
classify_mood(track_ids=[<candidate_local_id>], reclassify=false)
```

~5 seconds. Downloads a 30s clip, analyzes, deletes the clip.

### 3d — Add immediately if it passes

Check:
- `mood == target_mood`
- `mood_confidence >= min_confidence`

If passes:
```text
# Add to local playlist
manage_playlist(
  action="add_tracks",
  data={id: <playlist_id>},
  track_refs=["local:<candidate_id>"]
)

# Sync to YM right now (not at the end)
sync_playlist(playlist_id=<playlist_id>, direction="push")
```

If fails: discard (or archive the local track).

### 3e — Move to next seed

After processing all K recommendations for the current seed, move to the next track.
Tracks added in this round will be processed as seeds in the next round.

### 3f — Repeat rounds

Run `rounds` iterations total. Each round processes the full playlist (including
tracks added in the previous round). Stop early if `target_count` is reached.

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
