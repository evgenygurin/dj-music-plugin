# Render Stabilization — Design

> Date: 2026-07-08 · Status: approved · Branch: `feat/render-stabilization`

## Sections

1. import-linter contracts for domain.render + audio.render
2. Code quality pass (temp files, dedup, constants, re-exports)
3. `deliver_set` tool + handler
4. `render_verify` tool + handler (DJ-adapted mix-verify → MCP)

---

## 1. import-linter contracts

Add `[tool.lint.import-linter]` section to `pyproject.toml` enforcing:

- **`domain-render-pure`**: `app.domain.render` must not import `app.audio`, `app.handlers`, `app.tools`, `app.server`.
- **`audio-render-side-effect`**: `app.audio.render` must not import `app.handlers`, `app.tools`, `app.server`.

These catch accidental boundary violations and enforce the dependency rule (handlers orchestrate both; domain is pure; audio is side-effect).

### Files

| File | Action |
|------|--------|
| `pyproject.toml` | Add `[tool.lint.import-linter]` with 2 contracts |

---

## 2. Code quality pass

Four independent fixes:

### 2a. Temp files → workspace / tempfile

Current code writes to hardcoded `/tmp/_qa_{hash}.wav` and `/tmp/_scan.f32` — both risk collision under concurrent renders.

- `phase_refine.py:refine_phase`: replace `/tmp/_qa_{hash}.wav` with `tempfile.NamedTemporaryFile(suffix=".wav", delete=False)` or a `--scratch` dir under the workspace.
- `diagnostics.py:scan_mix`: replace `/tmp/_scan.f32` with `tempfile.NamedTemporaryFile(suffix=".f32")`.

### 2b. Deduplicate `_workspace()`

Both `app/shared/render_studio_data.py` and `app/resources/render.py` compute:

```python
Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"
```

- Extract to `app/shared/workspace.py`: `render_workspace(version_id: int) -> Path`.
- Both callers import from there.

### 2c. Magic numbers → constants

Duplicated across `kick_phase.py`, `phase_refine.py`, `diagnostics.py`:

- `_LP_HZ = 150`
- `_SR = 22050`
- `_HOP = 512`
- `_CLAMP_DB = 4.0` (in `levels.py`)

Move to `app/audio/render/_constants.py`:

```python
LP_HZ = 150
ANALYSIS_SR = 22050
HOP_LENGTH = 512
GAIN_CLAMP_DB = 4.0
```

All consumers import from `_constants`.

### 2d. Re-exports in `app/audio/render/__init__.py`

Handlers import individual modules:
```python
from app.audio.render.kick_phase import detect_kick_trim
from app.audio.render.phase_refine import refine_phase
from app.audio.render.runner import run_render
from app.audio.render.diagnostics import scan_mix, diagnose_mix
```

Add re-exports to `__init__.py` so handlers can do:
```python
from app.audio.render import detect_kick_trim, refine_phase, run_render, scan_mix, diagnose_mix
```

### Files

| File | Action |
|------|--------|
| `app/audio/render/_constants.py` | Create |
| `app/audio/render/__init__.py` | Add re-exports |
| `app/audio/render/kick_phase.py` | Import from `_constants`, remove local `_LP_HZ`, `_SR` |
| `app/audio/render/phase_refine.py` | Import from `_constants`, `tempfile` for temp WAV |
| `app/audio/render/diagnostics.py` | Import from `_constants`, `tempfile` for scan temp |
| `app/audio/render/levels.py` | Import `GAIN_CLAMP_DB` from `_constants` |
| `app/shared/workspace.py` | Create |
| `app/shared/render_studio_data.py` | Use `workspace.render_workspace` |
| `app/resources/render.py` | Use `workspace.render_workspace` |
| `app/handlers/render_beatgrid.py` | Use re-exported symbols |
| `app/handlers/render_mixdown.py` | Use re-exported symbols |
| `app/handlers/render_diagnose.py` | Use re-exported symbols |

---

## 3. `deliver_set` tool + handler

### Tool surface

```python
@tool(name="deliver_set", task=True)
async def deliver_set(
    version_id: Annotated[int, Field(ge=1)],
    out_dir: Annotated[str | None, Field(description="Override output dir")] = None,
) -> DeliverSetResult:
    ...
```

Returns `DeliverSetResult`:

```python
class DeliverSetResult(BaseModel):
    version_id: int
    out_path: str
    files: list[str]   # relative paths in the bundle
    n_tracks: int
    continuous_mix_included: bool
```

### Handler logic

`app/handlers/deliver_set.py`:

1. Resolve `set_id` from `version_id` via repo.
2. Read `get_render_inputs(version_id)` for track list + metadata.
3. Determine output dir: `out_dir or settings.delivery.output_dir / "deliver" / f"v{version_id}"`.
4. For each setting toggle in `DeliverySettings`:
   - `copy_audio_files`: copy source MP3s to `tracks/{k:02d}_{safe_title}.mp3`. Skip iCloud stubs (check `st_blocks * 512 >= st_size * icloud_min_download_ratio`).
   - `emit_m3u8`: generate `#EXTM3U` playlist with `#EXTINF` per track.
   - `emit_rekordbox_xml`: generate `DJ_PLAYLISTS` XML with COLLECTION + one playlist. Map Camelot → musical key (7A→Dm, 7B→F, etc.). File paths as `file://localhost/…`.
   - `emit_continuous_mix`: copy `MIX.mp3` from render workspace if it exists.
   - `emit_cheatsheet`: resolve set cheatsheet from resource path and save as `.txt`.
   - `emit_json_guide`: generate `guide.json` with version metadata + track list (BPM, key, gain, duration).
5. Return `DeliverSetResult`.

### Files

| File | Action |
|------|--------|
| `app/handlers/deliver_set.py` | Create |
| `app/tools/render/deliver_set.py` | Create |
| `app/schemas/delivery.py` | Create `DeliverSetResult` |
| `tests/handlers/test_deliver_set.py` | Create |
| `tests/tools/render/test_deliver_set_tool.py` | Create |

### Reuse from golden script

The golden script's `bundle()` is the reference — port its XML/M3U8 generation, track numbering, and key mapping into the handler. The golden script stays in place.

---

## 4. `render_verify` tool + handler (DJ-adapted mix-verify → MCP)

### Tool surface

```python
@tool(name="render_verify")
async def render_verify(
    version_id: Annotated[int, Field(ge=1)],
    skip_post: Annotated[bool, Field(description="Pre-render checks only")] = False,
) -> RenderVerifyResult:
    ...
```

Returns `RenderVerifyResult`:

```python
class RenderVerifyResult(BaseModel):
    version_id: int
    passed: int
    warned: int
    failed: int
    exit_code: int              # 0 = all pass, non-zero = any FAIL
    summary: str                # human-readable one-liner
    results: list[CheckResult]  # per-check detail
```

### Checks (14 total)

**Pre-render** (5) — run against source files + manifest:

| # | Check | What it catches |
|---|-------|-----------------|
| 1 | honest_duration | ffprobe bitrate-estimate lie vs decoded samples |
| 2 | bpm_reliability | onset BPM vs declared BPM per track |
| 3 | source_trim_bounds | trim outside decoded source length |
| 4 | boundary_alignment | segment starts/ends near beat grid |
| 5 | timeline | negative overlap, last track overrun |

**Post-render** (9) — run against MIX.mp3:

| # | Check | What it catches |
|---|-------|-----------------|
| 6 | output_duration | rendered length vs planned |
| 7 | clipping | peak ≥ -0.1 dBFS or clipped samples |
| 8 | dropouts | near-silent windows |
| 9 | loudness_consistency | per-segment LUFS spread > 6 LU |
| 10 | low_band_holes | kick/bass disappears while mix plays |
| 11 | stereo_balance | L/R imbalance > 4 dB or negative correlation |
| 12 | bpm_stability | BPM σ across 30 s windows > 5 |
| 13 | kick_consistency | kick drop events > 32 s |
| 14 | energy_range | RMS spread > 38 dB |

### Architecture

```
scripts/verify_mix/        ← untouched, production workflow
  manifest.py
  analysis.py
  checks.py
  report.py

app/audio/render/verify/   ← DJ-adapted port (this spec)
  __init__.py                 re-exports
  manifest.py                 DJManifest from RenderPlan
  analysis.py                 measure primitives (ported subset)
  checks.py                   14 checks (ported + adapted)
  report.py                   Report model (same shape)

app/handlers/render_verify.py
app/tools/render/render_verify.py
app/schemas/render.py        ← add RenderVerifyResult
```

Key differences from `scripts/verify_mix/`:
- **Manifest**: built from `RenderPlan` + beatgrid, not from JSON file.
- **No vocal_masking**: DJ mix has no isolated vocal layer.
- **No phase_alignment**: DJ mix has no backbone to phase-align layers against.
- **No tempo_ratio_sanity**: tempo ratio is always `target_bpm / source_bpm`.
- **Boundary alignment** simplified: segment starts/ends aligned to kick grid from `beatgrid.json`, not to a backbone beat grid.
- **Thresholds** (in `VerifyConfig`): same default values as mix-verify.

### Files

| File | Action |
|------|--------|
| `app/audio/render/verify/__init__.py` | Create |
| `app/audio/render/verify/manifest.py` | Create — `DJManifest` from `build_render_plan` output |
| `app/audio/render/verify/analysis.py` | Create — honest decode, BPM, beat grid, RMS, band energy, LUFS, crest, stereo, dips, kicks |
| `app/audio/render/verify/checks.py` | Create — 14 check functions |
| `app/audio/render/verify/report.py` | Create — Report (PASS/WARN/FAIL) |
| `app/handlers/render_verify.py` | Create |
| `app/tools/render/render_verify.py` | Create |
| `app/schemas/render.py` | Add `RenderVerifyResult` + `CheckResult` models |
| `tests/audio/render/verify/test_checks.py` | Create |
| `tests/handlers/test_render_verify.py` | Create |
| `tests/tools/render/test_render_verify_tool.py` | Create |

### Integration with render workflow

`render_mixdown_handler` may optionally call `render_verify_handler` after a successful render. Controlled by a config toggle (`render.auto_verify: bool = False` — not implemented in this spec; can be added later).

---

## Tests

Merge into the existing test suite — no new infrastructure:

| Area | Existing pattern | This spec |
|------|------------------|-----------|
| Domain | `tests/domain/render/test_levels.py` | No new domain tests (changes are all audio/shared) |
| Audio | `tests/audio/render/test_kick_phase.py` | New `tests/audio/render/verify/` |
| Handlers | `tests/handlers/test_render_beatgrid.py` | New `test_deliver_set.py`, `test_render_verify.py` |
| Tools | `tests/tools/render/test_render_beatgrid_tool.py` | New tool tests |
| Schemas | `tests/schemas/test_render_schemas.py` | Add verify + delivery schemas |

---

## Edge cases

| Scenario | Behaviour |
|----------|-----------|
| Render workspace missing | `render_verify` → WARN on post checks (source checks still run on files) |
| MIX.mp3 missing | `deliver_set` skips continuous mix, `emit_continuous_mix_included=False` |
| No beatgrid | `render_verify` boundary_alignment → WARN (skipped) |
| Source MP3 missing from disk | Both `deliver_set` and `render_verify` → WARN per missing file |
| iCloud stub file | `deliver_set` copies only if `st_blocks * 512 >= st_size * ratio` |
| Concurrent renders | Temp files now scoped to workspace/tempfile, no collision |
| Same version delivered twice | Overwrites files in the output dir (idempotent) |
