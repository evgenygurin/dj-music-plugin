---
description: Render a continuous beatmatched mix for a set version.
agent: dj-music
---

Render a mix:
1. Check the set version with `dj_entity_get(set_version, id=version_id, fields=full)`
2. Run beatgrid: `dj_render_beatgrid(version_id)`
3. Run mixdown: `dj_render_mixdown(version_id)`
4. Diagnose: `dj_render_diagnose(version_id)`

User request: $ARGUMENTS
