---
name: deliver-set
description: Export and deliver a completed DJ set — M3U8, Rekordbox XML, JSON guide, cheat sheet, YM sync
argument-hint: "[set_name] [format]"
---

Deliver a DJ set. Use the `deliver-set` skill for the full workflow.

Arguments (all optional):
- `set_name` — set to deliver (will prompt if not given)
- `format` — m3u8, rekordbox, json, cheatsheet, or all

Examples:
- `/deliver-set` — interactive delivery workflow
- `/deliver-set "Friday Night" rekordbox` — export as Rekordbox XML
- `/deliver-set "Peak Time" all` — export in all formats + YM sync
