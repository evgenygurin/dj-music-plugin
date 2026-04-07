---
name: deliver-set
description: "This skill should be used when the user asks to \"deliver set\", \"export set\", \"finalize set\", \"rekordbox export\", \"sync set to YM\", or \"generate cheat sheet\". Covers M3U8, Rekordbox XML, JSON guide, cheat sheet export and YM sync."
version: 0.5.0
---

# Deliver DJ Set Workflow

Guide the user through exporting a completed DJ set in various formats.

## Steps

1. **Review set quality first**
   - `quick_set_review(set_id=...)` — check for hard conflicts
   - If hard conflicts (score=0.0 transitions) exist, warn user
   - Suggest fixing before delivery, or proceed with acknowledgment

2. **Choose delivery method**

   ### Full Delivery Pipeline
   - `deliver_set(set_id=..., formats=["m3u8", "json_guide", "cheat_sheet"])`
   - Creates output directory: `generated-sets/{set_name}/`
   - Copies numbered MP3 files: `01. Track Title.mp3`, etc.
   - Generates all requested export files
   - Handles iCloud stubs (skips copy, references original path)

   ### Individual Export
   - `export_set(set_id=..., format="m3u8")` — M3U8 with DJ tags
   - `export_set(set_id=..., format="rekordbox_xml")` — Rekordbox compatible
   - `export_set(set_id=..., format="json_guide")` — full JSON with analytics
   - `export_set(set_id=..., format="cheat_sheet")` — human-readable transition notes

3. **Optional: Sync to Yandex Music**
   - `deliver_set(set_id=..., sync_to_ym=true)` — push as YM playlist
   - Or standalone: `push_set_to_ym(set_id=..., ym_playlist_name="...")`
   - If YM playlist exists, user chooses: overwrite / append / create new

4. **Verify output**
   - Check generated files in `generated-sets/` directory
   - Verify M3U8 plays correctly in DJ software
   - For Rekordbox: import XML via Rekordbox preferences

## Export Formats

| Format | Content | Use Case |
|--------|---------|----------|
| **M3U8** | Standard + `#EXTDJ-*` tags (BPM, key, energy, cues, transitions) | DJ software, media players |
| **Rekordbox XML** | Full Rekordbox-compatible XML with cues, loops, beatgrid | Rekordbox DJ import |
| **JSON Guide** | Structured JSON with per-track/transition details + analytics | Programmatic access, custom tools |
| **Cheat Sheet** | Human-readable text: BPM, key, transition type, score, warnings | Print for live DJ performance |

## Rekordbox Options

```text
export_set(set_id=..., format="rekordbox_xml", rekordbox_options={
    "include_cue_points": true,
    "include_saved_loops": true,
    "include_beatgrid": true,
    "include_sections": false
})
```

## Tips

- Use `dry_run=true` first to preview what would be generated
- iCloud stubs (not yet downloaded) are skipped during MP3 copy but referenced in M3U
- Cheat sheet is the most useful for live performance — print it!
- After delivery, the set is ready for import into Traktor, Rekordbox, or djay
