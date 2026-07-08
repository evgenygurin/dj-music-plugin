---
description: Build an optimized DJ set from a playlist or track pool.
agent: dj-music
---

Build a DJ set from the given pool. Steps:
1. If a playlist_id is given, list tracks with `dj_entity_list(playlist, id=playlist_id, include_relations=items)`
2. Score the pool with `dj_transition_score_pool(track_ids=[...])`
3. Optimize ordering with `dj_sequence_optimize(track_ids=[...])`
4. Create a set version with `dj_entity_create(set_version, data={...})`
5. Present the set using `dj_ui_set_view(set_id=..., version_id=...)`

User request: $ARGUMENTS
