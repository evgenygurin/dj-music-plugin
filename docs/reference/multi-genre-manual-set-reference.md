# Multi-Genre Manual Set Building — Quick Reference

> Created: 2026-09-03. Consolidates evidence from `reference/*`, `subgenre_presets.py`, `AGENTS.md`, external sources (Mixgraph, Vibes, Setflow, arXiv EDM research).

---

## 1. Constants Source (`app/config/subgenre_constants.json` / `.py`)

- **Presets (18):** 14 techno aliases (`industrial_techno`, `dub_techno`, `hard_techno`, `hypnotic_techno`, `peak_time_techno`, `driving_techno`, `acid_techno`, `raw_techno`, `tribal_techno`, `detroit_techno`, `deep_techno`, `minimal_techno`, `progressive_techno`, `melodic_techno`) + 4 house (`deep_house`, `tech_house`, `progressive_house`, `classic_house`).
- **Profiles (15 techno):** `minimal`, `hypnotic`, `driving`, `tribal`, `peak_time`, `acid`, `industrial`, `hard_techno`, `raw`, `dub_techno`, `melodic_deep`, `progressive`, `ambient_dub`, `detroit`, `breakbeat`.
- **House profiles (4):** `deep_house`, `tech_house`, `progressive_house`, `classic_house`.
- **Audit rules (9):** `BpmRangeRule` (120–155), `LufsRangeRule` (–20 to –4), `UnreliableBpmRule` (`bpm_confidence_min`: 0.5), `UnreliableKeyRule` (`key_confidence_min`: 0.4), `TooHarmonicRule` (`hp_ratio_max`: 8.0), `ExcessiveDynamicsRule` (`crest_factor_max`: 30.0), `NoiseSpectrumRule` (`spectral_flatness_max`: 0.5), `VariableTempoRule` (info), `ClippingRiskRule` (`true_peak_max`: 0.0).
- **Render defaults:** `target_bpm`: 130.0, `transition_bars`: 48, `body_bars`: 40, `xsplit_low_hz`: 250, `xsplit_high_hz`: 4000, `limiter_ceiling`: 0.85, `low_swap_beats`: 1.0.

---

## 2. Templates (`reference://templates` — 8)

| Template | Duration (min) | Slots | Key energy arc |
|---|---|---|---|
`roller_90` | 90 | 8 (minimal → hypnotic → driving → tribal → driving → hypnotic → driving → hypnotic) | Sustained drive |
`peak_hour_60` | 60 | 7 (driving → peak_time → acid → raw → industrial → peak_time → driving) | Relentless intensity |
`classic_60` | 60 | 8 (minimal → dub_techno → melodic_deep → progressive → driving → peak_time → hypnotic → melodic_deep) | Build-peak-release |
`wave_120` | 120 | 10 (wave cycles: minimal → progressive → peak_time → melodic_deep → hypnotic → driving → acid → minimal → peak_time → melodic_deep) | Multi-wave |
`progressive_120` | 120 | 10 (gradual build over 2h) | Slow ramp |
`closing_60` | 60 | 7 (drive → hypnotic → melodic_deep → progressive → dub_techno → minimal → ambient_dub) | Graceful end |
`warm_up_30` | 30 | 4 (ambient_dub → dub_techno → minimal → melodic_deep) | Low-energy opener |
`full_library` | 0 | 4 (free, flexible) | Any pool |

---

## 3. Multi-Genre Design Patterns

### Approach 1 (Manual — recommended)
`Template` (`reference://templates`) + `track_id` list + `render_plan.json` (`start_s`/`end_s`) + `render_set_workflow` (`stem=True`, `filter_sweep=None`, `echo=None`, `reverb=None`).

### Resource Template (polymorphic)
`local://genres/{genre}/subgenres` — returns JSON with `subgenres` array (name, BPM range, mood, preset, profile features).

### Prompt Template (polymorphic)
`manual_set_workflow` — parameters: `genre` (str, default `techno`), `subgenre` (str | None), `template` (str, default `roller_90`), `bpm_range` (list[int] | None), `mood` (str | None), `transition_bars` (int | None, default 48), `body_bars` (int | None, default 40), `camelot_mode` (str, default `soft`), `stem` (bool, default `True`), `filter_sweep` (str | None, default `None`), `echo` (str | None, default `None`), `reverb` (str | None, default `None`), `version_id` (int | None).

### Validation Gates
- `BpmRangeRule` (120–155 BPM) — fail if out.
- `Camelot` distance ≤ 2 — hard conflict if ≥ 3.
- `transition_bars` / `body_bars` — check segment overlaps in `render_plan.json`.
- Post-render: `render_validate_grid` (`|dev|` ≤ 0.5 ok, 0.5–1 warn, > 1 fail), `beatgrid.json` (`phase_ms` > 0.25 beats = gap).

---

## 4. Key Mathematical / Scientific Evidence (external)

- **BPM compatibility** (`Transition Scoring`): exponential decay `exp(-0.019 * pct^2)` where `pct = |from_bpm - to_bpm| / from_bpm * 100`. Seamless (<2%), comfortable (2–4%), noticeable (4–6%), creative needed (6–9%), jarring (≥9%).
- **Energy arc phases** (`Energy Planner`): warmup (stable/slight rise → score 1.0, wrong 0.5), build (rising → 1.0, wrong 0.3), peak (high/stable → 1.0, wrong 0.5), release (dropping → 1.0, wrong 0.3).
- **Camelot transition rules** (`Camelot` resource): same number = perfect, adjacent numbers = smooth, ±2 = acceptable, >2 = hard conflict.
- **Standard blend lengths** (Mixgraph, Vibes, Setflow): 32–64 bars standard (~30–60 sec @ 130 BPM); minimal can stretch 64+ bars; peak-time shorter (16–32 bars).
- **BPM distribution** (Setflow 2026): 120–129 BPM = 34.9% of tracks; 130–139 BPM = 12.4%; 150–159 BPM = 10.9%.
- **Subgenre BPM ranges** (Genre AI / PULSE / Vibes): `minimal` 125–130, `hypnotic` 130–142, `peak_time` 132–140, `acid` 130–145, `industrial` 135–150, `hard` 145–160, `dub` 120–128, `melodic` 120–127.
- **Structure** (TrackSensei): 16-bar phrases; intro 32–64 bars (min 16 bars for mix-in); outro 32–64 bars; arrangement: 32-bar blocks (intro → bass → stab → reduction → peak → outro) at 130 BPM = 195 bars (~6 min).
- **Switch point detection** (arXiv Zehren thesis): novelty in energy, harmony, timbre, drum onset density; phase-aligned on 4-bar periods; salience threshold (0.4 × max harmonic energy) for 4 bars after switch point.

---

## 5. Changes Applied (outdated info removed)

- `AGENTS.md`: shortened render lessons; removed outdated long checklist; added reference to `skills/validate-set/` and `rules/render.md`.
- `reference/subgenres.md`: updated from outdated "11 distinct presets" to current 18 entries (`PRESET_MAP`); kept deprecation note (`hypnotic_techno` deprecated for house) consistent with `subgenre_presets.py`.
- `docs/superpowers/specs/2026-09-03-manual-set-building-design.md`: design spec with multi-genre constants, polymorphic resource/template, validation gates, production risks.
- `docs/superpowers/plans/2026-09-03-manual-set-building-plan.md`: implementation plan with 6 tasks (constants, resource, prompt, integration, docs, execution).

---

## 6. Next Actions

- Confirm plan (`docs/superpowers/plans/2026-09-03-manual-set-building-plan.md`) to start execution.
- Confirm whether to create `app/config/subgenre_constants.json` (JSON) or `.py` (Python module) — current proposal uses JSON for portability, `.py` for type-checking.
- Confirm `transition_bars` override: 0 (dense mix) or 48 (standard blend) for manual builds.
