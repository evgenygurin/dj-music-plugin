# mix-verify

Verify an assembled multi-source track against its **build manifest** —
the JSON plan the ffmpeg graph is generated from. Reads the *same*
manifest the render used, so what is checked is exactly what was
rendered. Returns a PASS/WARN/FAIL report (text + optional JSON) and a
non-zero exit on any FAIL, so delivery can be gated.

Design: [`docs/superpowers/specs/2026-07-07-mix-verify-design.md`](../../docs/superpowers/specs/2026-07-07-mix-verify-design.md).

## Usage

```bash
# full verification (sources + rendered output)
uv run python -m scripts.verify_mix path/to/manifest.json

# gate delivery on it
uv run python -m scripts.verify_mix manifest.json && cp mix.mp3 out/

# pre-render only (sources + plan, no output file yet)
uv run python -m scripts.verify_mix manifest.json --pre-only

# machine-readable report
uv run python -m scripts.verify_mix manifest.json --json report.json
```

Paths in the manifest resolve relative to the manifest file's directory.

## Manifest

```json
{
  "output": "mix.mp3",
  "backbone": { "source": "backbone.wav", "bpm": 124.53, "bed": true },
  "layers": [
    {
      "source": "tokyo_vocals.wav",
      "role": "vocal",
      "src_trim": [15.7, 64.0],
      "tempo_ratio": 1.00024,
      "place_at": 0.0,
      "gain": 1.05
    }
  ]
}
```

- `role` ∈ `{vocal, bed}`
- `src_trim` = `[start_s, end_s]` in the source
- `tempo_ratio` = rubberband tempo applied (out time = src_dur / ratio)
- `place_at` = start offset on the final timeline
- `gain` = linear volume multiplier

## Checks

Pre-render (sources + manifest):

| check | fails when |
|---|---|
| `honest_duration` | ffprobe bitrate-estimate diverges > 2 % from the decoded sample-count length |
| `bpm_reliability` | measured backbone BPM (onset-autocorrelation, never `beat_track`) mismatches the declared BPM |
| `tempo_ratio_sanity` | `source_bpm × tempo_ratio` lands > ±1 BPM off the backbone |
| `phase_alignment` | placed layer downbeats drift > 0.15 of a beat off the backbone grid (approximate) |
| `source_trim_bounds` | a layer trim extends beyond the decoded source length |
| `boundary_alignment` | layer start/end boundaries are off the backbone beat/bar grid |
| `timeline` | vocal-on-vocal overlap, or a layer overrunning the bed |

Post-render (rendered output):

| check | fails when |
|---|---|
| `output_duration` | rendered length differs from the planned timeline by > 2 s |
| `vocal_masking` | isolated vocal-band (200 Hz–4 kHz) level is buried under the bed in its window |
| `level_jumps` | RMS jumps > 6 dB at a declared segment boundary |
| `clipping` | true peak/sample peak ≥ −0.1 dBFS, or clipped samples are present |
| `dropouts` | undeclared near-silent windows ≥ 0.5 s |
| `loudness_consistency` | per-segment integrated LUFS spread > 6 LU |
| `low_band_holes` | kick/bass band drops out for sustained windows |
| `stereo_balance` | severe L/R imbalance or negative mono-compatibility correlation |

Thresholds live in `VerifyConfig` (`checks.py`). Missing sources degrade
to WARN, never a crash.

## Dependencies

`numpy`, `librosa`, `scipy` (`[audio]` extra), `ffmpeg` + `ffprobe` on `PATH`.
