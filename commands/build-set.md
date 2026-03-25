---
name: build-set
description: Build an optimized DJ set from a playlist using GA or greedy algorithm
argument-hint: "[playlist_name] [template] [duration_min]"
---

Build a DJ set. Use the `build-set` skill for the full workflow.

Arguments (all optional):
- `playlist_name` — source playlist (will prompt if not given)
- `template` — one of: warm_up_30, classic_60, peak_hour_60, roller_90, progressive_120, wave_120, closing_60, full_library
- `duration_min` — target duration in minutes

Examples:
- `/build-set` — interactive guided workflow
- `/build-set Peak Time Techno peak_hour_60` — build from named playlist with template
- `/build-set "My Tracks" classic_60 90` — 90-minute classic set
