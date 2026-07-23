# Maximal Local Stem Tool Design

Date: 2026-07-22
Status: approved for implementation planning

## Goal

Build a new 10-12 minute techno DJ-performance tool from the local prepared stems in `/Users/laptop/Desktop/Stems`. The result should feel smarter and more harmonically controlled than a human 3-deck performance: it should rotate many compatible bass, drums, harmonic, instrumental, and occasional acappella layers while preserving groove, headroom, and musical direction.

The first version is local-only:

- No Suno generation.
- No database writes.
- No provider calls.
- No import of generated assets as `audio_file` entities.

## Source Material

The source directory is `/Users/laptop/Desktop/Stems`.

Observed catalog shape:

- 4,800 `.m4a` stem files.
- 960 unique tracks.
- Every track has all five stems: `acappella`, `bass`, `drums`, `harmonic`, `instrumental`.
- File names include index, BPM, genre, title, and stem type.

The implementation must treat all 960 complete tracks as the candidate universe. It must not hard-code a small favorite subset or repeatedly reuse the same 30 files unless the scoring genuinely selects them.

## Target Sound

Primary arc: hypnotic rolling techno into peak-time pressure.

Target shape:

- Intro: controlled hypnotic groove, low clutter.
- Build: progressively denser drums and harmonic motion.
- Pressure: 10-12 active stem layers with rotating drums, bass support, and texture.
- Peak release: driving/industrial/peak-time energy without uncontrolled hard-techno noise.
- Outro: controlled exit with mix handles.

Preferred target tempo: 132-134 BPM. The planner should pick one target BPM for the render and penalize stems that require extreme time-stretching.

## Layering Rules

The final track should use maximal layering, but not uncontrolled summing.

Default active layer budget:

- 2-3 drum layers.
- 1 full bass leader.
- 0-1 ghost bass or low-cut bass texture.
- 2-4 harmonic or texture layers.
- 1-2 low-gain instrumental beds.
- 0-2 short acappella chops or throws used as effects, not a lead vocal.

Hard rules:

- Never run two full-range bass leaders at the same time.
- At least one drum layer must provide stable kick/downbeat drive during pressure sections.
- Acappella layers must be short and sparse unless explicitly promoted by a later design change.
- Instrumental beds must stay low enough to glue the mix without masking drums or bass.
- Rotation must happen every 4-8 bars so the tool evolves instead of looping statically.

## Architecture

Create a local production path in the style of `scripts/render_local_12deck_stem_set.py`, but with an analysis-first planner rather than fixed curation.

Pipeline:

1. `StemCatalog`
   - Parse the Desktop stems directory.
   - Group files by track index.
   - Validate that each selected candidate has all five required stems.

2. `StemFeatureScan`
   - Compute fast per-stem features needed for compatibility and gain staging.
   - Features include loudness proxy, low/mid/high energy, spectral centroid or brightness, onset density for drums, and a lightweight harmonic/chroma proxy for harmonic/instrumental/acappella stems.
   - Cache scan output in the render output directory so reruns do not rescan unchanged files unnecessarily.

3. `CompatibilityScorer`
   - Score candidate stems for BPM stretch cost, genre fit, low-end conflict, drum density compatibility, harmonic clash, novelty, and section suitability.
   - Favor hypnotic/dub/progressive/minimal/detroit material early and driving/industrial/peak_time material later.

4. `ArrangementPlanner`
   - Build a 10-12 minute timeline matrix.
   - Each matrix event references one source stem, start/end time, gain, pan, EQ constraints, fade shape, and role.
   - Rotate 1-3 layers every 4-8 bars.
   - Track source reuse so the output explores the full catalog instead of overusing one cluster.

5. `LayerRenderer`
   - Render the matrix with ffmpeg.
   - Use per-layer gain staging, HPF/LPF where needed, fades, optional sidechain-style ducking or static ducking for bass/drum conflicts, master EQ, loudnorm/limiter.
   - Output a high-quality MP3 and retain a JSON manifest for reproducibility.

6. `QA`
   - Run the existing audio diagnostics where practical.
   - Report true peak, level jumps, near-silent windows, bass-thin regions, and layer-density summary.

## Outputs

Create a new output directory under `generated-sets/`, for example:

`generated-sets/maximal-stem-tool-2026-07-22/`

Expected artifacts:

- `MAXIMAL_STEM_TOOL_FINAL.mp3`
- `manifest.json`
- `features-cache.json`
- `diagnostics.json`
- Optional part renders if the renderer splits long ffmpeg graphs into sections.

The manifest must include:

- Source directory.
- Target BPM.
- Global duration.
- Every selected stem event with source path, role, start/end, gain, fade, EQ, and compatibility score.
- Reuse counts by source track and genre.
- QA summary.

## Error Handling

Fail early with a clear message when:

- The stems directory is missing.
- No files match the expected naming pattern.
- A selected track is missing one of the five required stems.
- ffmpeg or rubberband support is unavailable.
- The planner cannot meet the target layer density without violating hard bass/drum rules.

When analysis of a single file fails, the scanner should skip that file or track with a warning and continue if enough valid material remains.

## Testing And Verification

Implementation should include focused tests for pure planning logic where practical:

- Catalog parsing groups five stems into complete tracks.
- Arrangement never schedules two full bass leaders together.
- Layer count stays within the requested 10-12 layer budget during pressure sections.
- Rotation changes at least one layer every 4-8 bars.
- Planner uses a broad source set instead of a tiny repeated subset.
- Manifest shape is stable and reproducible.

Runtime verification for the produced track:

- Render completes without ffmpeg errors.
- Diagnostics report no dropouts and no severe level jumps.
- True peak stays below limiter ceiling.
- Manifest confirms broad catalog usage.

## Non-Goals

- No Suno generation in the first version.
- No Yandex Music sync.
- No permanent database import.
- No GUI or MCP tool surface in the first version.
- No attempt to process all 960 tracks simultaneously in one ffmpeg graph.
