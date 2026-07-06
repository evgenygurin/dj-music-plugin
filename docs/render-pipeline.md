# Render Pipeline

Turns a persisted `set_version` into a continuous, beatmatched MP3 — the same
result the hand-written `generated-sets/hypnotic-roller-90-FINAL/render_pipeline.py`
script produced, but generic (any version), testable, and wired into the
project's bounded contexts. Plan 1 builds the **engine only**: no MCP tools, no
Prefab UI. It is callable from the three handlers below.

The engine splits cleanly along the project's dependency rule:
**pure math** in `app/domain/render/` (no IO — imports only `models` + `shared`,
enforced by an `import-linter` contract) vs **side-effect DSP** in
`app/audio/render/` (librosa / scipy / ffmpeg subprocess, imported only by
handlers). A batch DB query (`SetVersionRepository.get_render_inputs`) feeds the
engine; three handlers orchestrate DB → engine → workspace files, with an
in-process `RenderJobRegistry` carrying live status.

**Reference (source of truth for the numbers):**
`generated-sets/hypnotic-roller-90-FINAL/render_pipeline.py` stays in the repo as
the golden script — the domain tests assert the ported math matches it exactly.

## Module Layout

```text
app/config/render.py              RenderSettings (DJ_RENDER_*)
app/domain/render/                pure compute — no IO
├── models.py                     TrackInput, TrackSegment, RenderPlan, BeatgridEntry
├── timeline.py                   build_render_plan, timeline_windows
├── levels.py                     gains_to_median (LUFS → gain)
└── graph.py                      build_filtergraph (ffmpeg filter_complex string)
app/audio/render/                 side-effect DSP — imported only by handlers
├── kick_phase.py                 detect_kick_trim
├── phase_refine.py               refine_phase
├── runner.py                     build_ffmpeg_cmd, run_render
└── diagnostics.py                scan_mix, diagnose_mix
app/repositories/set.py           SetVersionRepository.get_render_inputs
app/shared/render_jobs.py         RenderJobRegistry (leaf) + RENDER_JOBS
app/schemas/render.py             RenderBeatgridResult / RenderMixdownResult / RenderDiagnosticsResult
app/handlers/render_beatgrid.py   grid → beatgrid.json
app/handlers/render_mixdown.py    grid + plan → MIX.mp3
app/handlers/render_diagnose.py   mix → diagnostics.json
```

## Config — `RenderSettings` (`app/config/render.py`)

`RenderSettings` (env prefix `DJ_RENDER_`, registered on the `Settings`
aggregate as `settings.render`) holds every magic number the original script had
inline: `target_bpm` (130.0 — all tracks are stretched to this), `transition_bars`
(32 — overlap length between adjacent tracks), `body_bars` (24 — solo time per
track between blends), `xsplit_hz` (180 — the low/high crossover for the EQ bass
swap), `low_swap_bars` (2 — the low-band crossfade window), `outro_fade_bars`
(12 — end-of-mix fade), `limiter_ceiling` (0.85), and `workspace_subdir`
(`render`). The `beat_s` / `bar_s` properties derive seconds-per-beat and
seconds-per-bar from `target_bpm`.

## Domain — pure compute (`app/domain/render/`)

**`models.py`** — the four frozen, slotted dataclasses the engine passes around.
`TrackInput` is one set-version track as the DB hands it over
(track_id, yandex_id, title, bpm, key_code, mix_in_ms, integrated_lufs,
file_path) with a `tempo_ratio(target_bpm)` helper. `BeatgridEntry` is one
`beatgrid.json` row — the raw kick anchor plus QA corrections — with an
`effective_trim` property that prefers the refined trim when QA ran.
`TrackSegment` is a track already placed on the mix timeline (stretched,
kick-aligned, with `d_in_s` / `d_out_s` overlap durations and `start_s`).
`RenderPlan` is a fully-resolved render: the ordered `TrackSegment` list plus the
DSP constants the filtergraph needs.

**`timeline.py`** — the placement math, ported numbers-preserving from the
script's `_segment_sequence` + overlap loop. `build_render_plan(inputs, grid, …)`
computes each segment's incoming / outgoing transition durations
(`transition_bars * bar_s`), its total length (`body_bars * bar_s + d_in + d_out`),
its start on the timeline (`running_t += length - d_out`), and folds in the
per-track trim + gain from the beatgrid — returning a `RenderPlan`. The companion
`timeline_windows(…)` maps segments and their transition windows onto the
timeline (from the script's `boundaries`) for downstream inspection.

**`levels.py`** — `gains_to_median(lufs_by_track)` computes per-track loudness
match: gain each track toward the median integrated LUFS, clamped to ±4 dB.
Full-track integrated LUFS is far more reliable than the intro-chunk RMS the
script originally tried; tracks missing a LUFS value get 0.0 gain, and the median
is taken only over tracks that have one.

**`graph.py`** — `build_filtergraph(plan)` is a pure string builder for the
ffmpeg `filter_complex` graph (ported from the script's `render()`), returning the
list of statements the runner joins with `;`. Per segment `i` it reads input
`[i:a]`, does `atrim → rubberband=tempo=<ratio> → volume=<gain>dB` (the beatmatch
stretch to `target_bpm`), then splits the signal at `xsplit_hz` into a low band
(`lowpass`) and high band (`highpass`) so the two can be crossfaded independently
— the **EQ bass-swap transition**: the high band uses full-length `afade` qsin
in/out over the 32-bar transitions, while the low band swaps only over the short
`low_swap_bars` window centred on each transition (so two kicks never stack). Each
segment is `adelay`-ed to its slot, all segments `amix`-ed together, and the sum
runs through a final `alimiter` at `limiter_ceiling`. The last segment gets an
`outro_fade_bars` fade instead of an outgoing transition. The builder is
deterministic — a golden test pins the exact graph.

## Audio — side-effect DSP (`app/audio/render/`)

**`kick_phase.py`** — `detect_kick_trim(file_path, start_s, bpm)` finds the phase
anchor: low-pass to ~150 Hz to isolate the kick, run librosa onset + beat
tracking on that band, and take the first detected kick (not any onset — a
melodic pickup before the downbeat would misalign the grid) as the trim, returned
as `start_s + first_kick_offset` so the render starts exactly on a kick.

**`phase_refine.py`** — `refine_phase(file_path, base_trim_s, bpm, target_bpm)`
does the sub-beat correction (ported from `qa()`): pre-stretch a 24 s chunk to the
target BPM via ffmpeg rubberband, take the kick onset envelope, and
cross-correlate it against an ideal target-BPM pulse comb to find the exact
sub-beat offset. It returns `(phase_delta_ms, refined_trim_s)` so every track's
kicks land on the *same* grid, not just each track's own downbeat.

**`runner.py`** — `build_ffmpeg_cmd(plan, out_path)` assembles one `-i <file>`
per segment (in index order, matching the `[i:a]` references in the graph) plus
the joined `filter_complex`, `-map [mix]`, and `libmp3lame -b:a 320k` output.
`run_render(plan, out_path)` runs it, raising a typed `RuntimeError` on a missing
ffmpeg binary (needs one built with `librubberband`) or a non-zero exit.

**`diagnostics.py`** — post-render defect analysis (ported from `scan()` +
`diagnose()`), returning dataclasses instead of printing. `scan_mix(path)` is the
coarse whole-file pass: duration, `volumedetect` true-peak, clip risk, >6 dB
level jumps, and near-silent seconds. `diagnose_mix(path)` is the per-4s sweep
that tags each window (`LEVEL-JUMP`, `DROPOUT`, `bass-thin`, …) so a bad
transition can be located in time.

## Repository — `get_render_inputs` (`app/repositories/set.py`)

`SetVersionRepository.get_render_inputs(version_id)` is the generic DB source that
replaces the script's hardcoded `TRACKS` / `DB_LUFS`. It runs one batch query
joining `dj_set_items ⋈ tracks ⋈ track_audio_features_computed ⋈
dj_library_items`, ordered by `sort_index`, and returns a list of `TrackInput`
(yandex_id parsed best-effort from the on-disk `… [YID].mp3` filename). It raises
a typed `ValidationError` when a track has no registered audio file (download
first — mirrors the L5 finalization contract) or no BPM feature (analyze first).

## Handlers — orchestration (`app/handlers/render_*.py`)

**`render_beatgrid.py`** — pulls `get_render_inputs`, runs `detect_kick_trim` +
`refine_phase` per track, folds in `gains_to_median`, flags tracks whose phase
correction (>40 ms) or gain (>1.5 dB) was large, and writes `beatgrid.json`
(cached — re-reads it unless `refresh`). DSP calls are module-level so tests can
monkeypatch them without importing librosa/ffmpeg.

**`render_mixdown.py`** — auto-runs the beatgrid if missing (like
`sequence_optimize` auto-scores), reconstructs the `BeatgridEntry` map, calls
`build_render_plan`, registers a `RenderJob`, runs `run_render` to `MIX.mp3`,
then `scan_mix`-es the result — returning a `RenderMixdownResult` with duration,
true-peak, and defect counts. The job's error is recorded on failure before
re-raising.

**`render_diagnose.py`** — runs `diagnose_mix` on a rendered file, writes
`diagnostics.json`, and returns a `RenderDiagnosticsResult`.

## Status — `RenderJobRegistry` (`app/shared/render_jobs.py`)

A thread-safe, in-process registry (`RENDER_JOBS` singleton) of `RenderJob`
records (job_id, version_id, phase, progress/total, out_path, error, done). It
lives in `app.shared` (a leaf) so that the Plan-2 `local://render/jobs/{id}/status`
resource — which must not import `app.handlers` — can read live status even when
the host does not support the MCP task protocol.

## Workspace layout

Handlers write per-version artefacts under
`generated-sets/render/v{version_id}/` (`DeliverySettings.output_dir` /
`RenderSettings.workspace_subdir` / `v{version_id}`):

```text
generated-sets/render/v{version_id}/
├── beatgrid.json      per-track trim / refined_trim / gain / phase_ms / flags
├── MIX.mp3            the rendered continuous mix
└── diagnostics.json   per-window scan report
```

## MCP surface

The engine is exposed as MCP through thin `@tool` dispatchers
(`app/tools/render/`) that inject the clock + workspace path and delegate to
the handlers above, five read-only resources (`app/resources/render.py`), and
one workflow prompt. Everything is keyed by `version_id` — generic over any
persisted `set_version`.

### Tools (3, namespace `render`)

All three are heavy DSP passes and are declared `task=True` — the host runs
them as background tasks (requires `FastMCP(tasks=True)`, wired in
`app/server/app.py`, plus the `fastmcp[tasks]` extra). They are visible by
default (like `sync` / `compute`) and whitelisted in `ALWAYS_VISIBLE_TOOLS`
(`app/server/transforms.py`) so `BM25SearchTransform` never hides them.

| Tool | Params | Delegates to |
|---|---|---|
| `render_beatgrid` | `version_id`, `refresh=false` | `render_beatgrid_handler` → `beatgrid.json` |
| `render_mixdown` | `version_id`, `out_name?`, `transition_bars?`, `body_bars?`, `refresh_grid=false` | `render_mixdown_handler` → `MIX.mp3` |
| `render_diagnose` | `version_id`, `mix_path?` | `render_diagnose_handler` → `diagnostics.json` |

`render_mixdown` auto-runs the beatgrid when missing (like `sequence_optimize`
auto-scores). `render_diagnose` rejects a missing mix with a typed
`ValidationError` ("run render_mixdown first").

### Resources (5)

Cheap reads only — the module imports only `app.shared` / `app.domain` /
`app.config` / `app.repositories` (never `app.handlers`), so the heavy librosa
sweep stays in the `render_diagnose` tool.

| URI | Reads |
|---|---|
| `reference://render/defaults` | `RenderSettings` constants (target BPM, bars, XSPLIT, limiter) |
| `local://render/jobs/{job_id}/status` | Live progress from the in-process `RENDER_JOBS` registry |
| `local://render/jobs/{job_id}/diagnostics` | Saved `diagnostics.json` for the job's version workspace |
| `local://render/{version_id}/beatgrid` | Saved `beatgrid.json` |
| `local://render/{version_id}/timeline` | Segment + transition-window timeline (pure `timeline_windows` math) |

The `jobs/{job_id}/*` resources parse `v{version_id}[-{ts}]` out of the job id;
a malformed job id raises the typed `NotFoundError`, not a bare `ValueError`.

### Prompt

`render_set_workflow(version_id)` (namespace `workflow`, tag `delivery`) is the
pure-text recipe: ensure every track has a registered `audio_file`
(download first — the engine never downloads), optionally bring the set to
`analysis_level=5`, `render_beatgrid` → inspect `local://render/{id}/beatgrid`,
`render_mixdown`, `render_diagnose` → read `local://render/{id}/timeline` to
tell a transition-window hole (a defect) from a track's own breakdown (music),
then run `deliver_set_workflow`.

### Delivery reuse

`DeliverySettings.emit_continuous_mix` (env `DJ_DELIVERY_EMIT_CONTINUOUS_MIX`,
default `true`) makes `deliver_set_workflow` include the rendered
`render/v{version_id}/MIX.mp3` in the deliverable bundle alongside the M3U8 /
rekordbox XML / cheatsheet.

Prefab render studio (`ui_render_studio`) — see Plan 3
(`docs/superpowers/plans/2026-07-06-render-mcp-surface.md` § Next plan).
