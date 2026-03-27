---
name: expand-playlist
description: Use when expanding a techno subgenre playlist (minimal, acid, dub, etc.) with new tracks from Yandex Music. Covers the full pipeline from seed import to classification and YM sync.
---

# Expanding a Techno Subgenre Playlist

Full pipeline for growing a subgenre playlist (e.g. Minimal Techno) with properly classified tracks.

## CRITICAL: Start with Seed Tracks

**Before calling `expand_playlist_ym`, the playlist MUST contain seed tracks.**

`expand_playlist_ym` uses existing tracks as reference points for LLM/YM search.
An empty playlist produces generic or off-genre results.

**Minimum seeds: 5–10 representative tracks** of the target subgenre.

---

## Step 1 — Seed the Playlist

### Option A: Import from YM search (no local files needed)

```text
# 1. Find seed tracks by known artist
ym_search(query="Richie Hawtin minimal techno", type="tracks", limit=5)
ym_search(query="Magda techno minimal", type="tracks", limit=5)
ym_search(query="Ricardo Villalobos minimal", type="tracks", limit=5)

# 2. Import seeds (metadata only, no audio download)
import_tracks(
  track_refs=["ym:111", "ym:222", ...],
  playlist_id=<target_playlist_id>,
  auto_analyze=false
)
```

### Option B: Use existing library tracks

```text
filter_tracks(mood="minimal", limit=10)
manage_playlist(action="add_tracks", data={id: <playlist_id>}, track_refs=[...])
```

---

## Step 2 — Classify Seeds (L1+L2 Analysis)

Triggers auto-download of 30s clips → analysis → clip deleted:

```text
classify_mood(playlist_id=<playlist_id>, reclassify=false)
```

- Runtime: ~5 sec/track, 6 parallel threads
- Persists `mood` and `mood_confidence` to DB
- Required before `expand_playlist_ym` so seeds have features

**Check results:**

```text
audit_playlist(playlist_id=<playlist_id>, check="techno_quality")
```

Remove tracks with `mood_confidence < 0.3` or wrong subgenre.

---

## Step 3 — Expand

```text
expand_playlist_ym(
  playlist_id=<playlist_id>,
  target_count=50,
  strategy="llm"
)
```

Claude Code generates search queries like:
- `"Surgeon minimal techno dark"`, `"Speedy J abstract techno"`, `"Basic Channel dub"`

Results are auto-imported and analyzed (L1+L2).

**Alternative strategy:** `strategy="ym_recommendations"` — slower, less control.

---

## Step 4 — Re-classify and Distribute

```text
# Re-classify new additions
classify_mood(playlist_id=<playlist_id>, reclassify=false)

# Check distribution
audit_playlist(playlist_id=<playlist_id>)

# Distribute across subgenre playlists
distribute_to_subgenres(source_playlist_id=<playlist_id>, dry_run=true)
distribute_to_subgenres(source_playlist_id=<playlist_id>, sync_to_ym=true)
```

---

## Step 5 — Sync to YM (optional)

```text
sync_playlist(playlist_id=<playlist_id>, direction="push", dry_run=true)
sync_playlist(playlist_id=<playlist_id>, direction="push")
```

albumId is resolved automatically — pass bare YM track IDs.

---

## Minimal Subgenre Discriminators

Classifier features that define `minimal` (from `MoodClassifier`):

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
| classify_mood L1+L2 | 50 | ~1.5 min |
| expand_playlist_ym | +30 new | ~3 min total |
| distribute_to_subgenres | 80 | ~30 sec |

---

## Gotchas

- `import_tracks` without `auto_analyze=true` skips audio — do `classify_mood` explicitly after
- `expand_playlist_ym` strategy `"llm"` requires Claude to generate `search_queries` param (client-driven mode) — see `llm_discovery_workflow` prompt
- `distribute_to_subgenres` creates YM playlists if they don't exist yet — confirm with `dry_run=true` first
- After `sync_playlist`, always re-fetch to get fresh revision before next modification
