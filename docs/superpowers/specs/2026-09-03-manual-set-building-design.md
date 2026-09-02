# Manual Set Building Design (2026-09-03)

## 1. Research question
How to build a DJ techno set manually (without auto-generation) using the dj-music-plugin MCP, leveraging existing templates, subgenre profiles, Camelot compatibility, render defaults, and audit rules.

## 2. Evidence inspected
- Source: `reference://templates` (8 templates: warm_up_30, classic_60, peak_hour_60, roller_90, progressive_120, wave_120, closing_60, full_library) — official JSON.
- Source: `reference://subgenres` (15 techno subgenre profiles with feature weights and tolerances) — official JSON.
- Source: `reference://render/defaults` (target_bpm 130.0, transition_bars 48, body_bars 40, xsplit, limiter, EQ ratios) — official JSON.
- Source: `reference://audit_rules` (9 rules: BpmRangeRule 120-155, LufsRangeRule -20 to -4, UnreliableBpm/Key, VariableTempo, TooHarmonic, ExcessiveDynamics, NoiseSpectrum) — official JSON.
- Source: `reference://camelot` (compatibility edges distance <= 2) — official resource.
- Secondary evidence: Mixgraph (blend length 32-64 bars standard), Vibes (phrase-aligned 16/32 bar phrases), Setflow 2026 analysis (most common transition same-key 8A->8A, BPM window 120-129 dominates 34.9%).
- Code: `generated-sets/render/v249/render_plan.json` and `beatgrid.json` show segment overlaps and phase measurements — official render artifacts.

## 3. Selected approach: Approach 1 (recommended)
**Manual set = Template (`reference://templates`) + hand-curated `track_id` list + `render_plan.json` + `render_set_workflow`.**

### Why this approach
- Uses native plugin resources (`templates`, `subgenres`, `camelot`, `audit_rules`, `render/defaults`) rather than inventing new logic.
- Keeps full control over track order and transition lengths, avoiding the silence/gap issue observed in v249 (automatic 48-bar transition after last track when `transition_bars` not overridden).
- Allows direct validation via `render_validate_grid` and `local://render/{version_id}/grid_check`.

### Template selection
Choose from `reference://templates` based on scenario:
- `roller_90` — sustained driving energy, 90 min, 8 slots.
- `peak_hour_60` — relentless intensity, 60 min.
- `classic_60` — build-peak-release arc.
- `closing_60` — graceful ending.
For manual builds, `roller_90` or `peak_hour_60` are standard professional templates.

### Data flow
1. Select template → read `reference://templates`.
2. Curate `track_id` list manually (library search or known IDs).
3. Check BPM (`track_features.audio_bpm`) against `BpmRangeRule` (120-155) and stability (`audit_bpm_confidence_min` 0.5).
4. Check key (`track_features.audio_key_code`) against `reference://camelot` (distance <= 2 preferred).
5. Check mood (`track_features.mood`) against `reference://subgenres` profile if mono-style set required.
6. Build `render_plan.json` segments with `start_s`, `end_s` per track; set `transition_bars` (default 48 or manual override, e.g., 0 for tight mix) and `body_bars` (default 40 or override, e.g., 16 for shorter body).
7. Call `render_set_workflow` (or `dj_render_mixdown`) with `stem=True`, `filter_sweep=None`, `echo=None`, `reverb=None` (per AGENTS.md render lessons #2, #6).
8. Run post-render QA: `dj_render_diagnose` + `dj_render_validate_grid` (reading `local://render/{version_id}/grid_check`).

### Render parameters (defaults vs manual override)
- `target_bpm`: 130.0 (`reference://render/defaults`).
- `transition_bars`: 48 (default) — for manual dense mix can be set to 0 or 16.
- `body_bars`: 40 (default) — can be reduced to 32 or 16 if shorter track bodies needed.
- `subgenre`: `hypnotic_techno` (default) — matches `roller_90`/`peak_hour_60` profiles.
- `stem`: `True` (default, Demucs 4-stem) — do not change to `False` (classic EQ sounds cheap per AGENTS.md lesson #6).
- Effects (`filter_sweep`, `echo`, `reverb`): must be explicitly `None` to avoid default preset artifacts (AGENTS.md lesson #2, #6).

### Validation gates
- `BpmRangeRule` (120-155 BPM) — fail if out of range.
- `Camelot` distance <= 2 — hard conflict if >= 3 (standard for professional mix).
- `transition_bars` / `body_bars` — check `render_plan.json` segment overlaps; total mix length = last `end_s` (e.g., v249 total ~886 s ≈ 14:46).
- Post-render: `render_validate_grid` checks BPM drift (`bpm_measured` vs `audio_bpm`) and phase alignment (`phase_ms`); thresholds from `reference://render/validation` (|dev| <= 0.5 ok, 0.5-1 warn, >1 fail).

### Testing implications
- Before commit: verify `render_plan.json` has non-null `transition_bars` and `body_bars` (or explicit 0) — this fixes the v249 silence issue.
- After render: verify `generated-sets/render/v<version>/stems/` is non-empty (Demucs stems required for `stem=True`).
- Verify `MIX.mp3` duration ≈ last segment `end_s`; if silence appears, inspect `beatgrid.json` phase offsets (> 0.25 beats indicates transition gap) and adjust `transition_bars`.

## 4. Production risks and adaptations
- If `stems` directory empty after render, `stem=True` falls back to classic EQ (`stem=False`), which produces lower quality (AGENTS.md lesson #7). Solution: ensure Demucs is available (`demucs` in path) before calling `dj_render_mixdown`.
- Manual `render_plan.json` requires correct `start_s` / `end_s` per segment; overlapping segments should have `start_s` before previous `end_s` and `end_s` after previous `start_s` + `body_bars`.
- `transition_bars`: 48 bars is ~88 sec at 130 BPM; for dense mix, set to 0 or 16 to avoid silence after track ends (as observed in v249 at 9:30).

## 5. Open questions
- Does user prefer `roller_90` or `peak_hour_60`? (Selected approach supports either; template is configurable in `render_plan.json`.)
- Should `transition_bars` be set to 0 for manual dense mix, or kept at 48 for standard professional blend?
- Should `body_bars` be reduced from 40 to 32 for shorter mix duration?

## 6. Evidence references
- `reference://templates` (JSON, 8 templates)
- `reference://subgenres` (JSON, 15 profiles)
- `reference://render/defaults` (JSON: 130 BPM, 48/40 bars)
- `reference://audit_rules` (JSON: 9 rules with thresholds)
- `reference://camelot` (compatibility edges <= 2)
- `AGENTS.md` render lessons (#2, #6) — effect nulls, `stem=True`, no gain adjustments.
- `generated-sets/render/v249/render_plan.json` — segment overlaps, `null` `transition_bars`/`body_bars`.
- External sources: Mixgraph blend length 32-64 bars; Vibes phrase-aligned 16/32 bar; Setflow BPM analysis 120-129 dominant.

## 7. Decision confirmation (user approved)
User approved Approach 1 (`“да”`). Design uses `reference://templates`, `reference://subgenres`, `reference://camelot`, `reference://audit_rules`, `reference://render/defaults`, and `AGENTS.md` render lessons.
