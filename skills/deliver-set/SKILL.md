---
name: deliver-set
description: "Use when the user asks to deliver a set, export a set, finalize a set, do a rekordbox export, sync a set to YM, or generate a cheat sheet. Covers M3U8, Rekordbox XML, JSON guide, cheat sheet export and YM sync."
version: 1.0.1
---

# Deliver DJ Set Workflow

Guide the user through exporting a completed DJ set via the v1 polymorphic dispatchers. See @docs/tool-catalog.md (13 dispatchers + 27 resources + 6 prompts).

## Steps

1. **Review set quality first**
   - Read `local://sets/{id}/review` — hard conflicts (score=0.0) surface here
   - If conflicts exist, warn the user and suggest fixing (see skill `build-set` — replacement / new version) before delivery

2. **Ensure audio files on disk (L4)**
   - Deliver needs local MP3 files. Download and level-up to L4:
     `entity_create(entity="audio_file", data={"track_ids": [...], "persistent": true})`
     (handler `audio_file_download` fetches MP3 from provider + registers `DjLibraryItem` + bumps features to L4 / structure)
   - Downloads are idempotent; existing files are skipped.

3. **Use the `deliver_set_workflow` prompt**
   - This is the canonical recipe. It chains scoring → conflict gate (elicitation) → file write → optional YM sync:
     `deliver_set_workflow(set_id=<id>, formats=["m3u8","json","cheatsheet"], sync_to_ym=false)`
   - Prompts live in `app/prompts/`; list via `list_prompts` MCP method.

4. **Inspect output resources**
   - Cheat sheet: `local://sets/{id}/cheatsheet?version=<v>`
   - Narrative: `local://sets/{id}/narrative`
   - Full view: `local://sets/{id}/full`
   - Files land in `generated-sets/{sanitized_set_name}/` — numbered MP3 copies + format artifacts.

5. **Optional: Sync to Yandex Music**
   - Namespace `sync` is locked by default. Unlock once per session:
     `unlock_namespace(namespace="sync", action="unlock")`
   - Push the set's linked playlist: `playlist_sync(playlist_id=<set.linked_playlist_id>, direction="push", source="yandex", dry_run=false)`
   - To create a fresh YM playlist first:
     `provider_write(provider="yandex", entity="playlist", operation="create", params={"name": "..."})`
     then add tracks: `provider_write(provider="yandex", entity="playlist", operation="add_tracks", params={"kind": <kind>, "track_ids": [...], "revision": <rev>})`
     (`provider:write` also needs unlock)

6. **Verify output**
   - Inspect `generated-sets/` directory
   - Play M3U8 in the target DJ software
   - For Rekordbox: import the XML via Rekordbox preferences

## Export Formats

| Format | Content | Use Case |
|--------|---------|----------|
| **M3U8** | Standard + `#EXTDJ-*` tags (BPM, key, energy, cues, transitions) | DJ software, media players |
| **Rekordbox XML** | Full Rekordbox-compatible XML with cues, loops, beatgrid | Rekordbox DJ import |
| **JSON Guide** | Per-track / per-transition details + analytics | Programmatic access, tooling |
| **Cheat Sheet** | Human-readable text: BPM, key, transition type, score, warnings | Print for live DJ performance |

Valid values passed to the workflow prompt: `m3u8`, `rekordbox`, `json`, `cheatsheet`. Default if omitted: `["m3u8", "cheatsheet"]`.

## Tips

- `dry_run=true` on `playlist_sync` previews YM mutations without applying — use before push
- Delivery auto-triggers L4 (structure + permanent MP3) via the `audio_file_download` handler — no need for a separate analyze call
- iCloud stubs (file < 90% of expected size) are skipped during copy but still referenced in the M3U
- Hard conflicts trigger an elicitation inside `deliver_set_workflow` — answer `continue` or `abort`
- Tool reference: @docs/tool-catalog.md; @docs/reports/tiered-analysis-design-2026-03-27.md (tiered analysis)
- After delivery, the set is ready for import into Traktor, Rekordbox, or djay
