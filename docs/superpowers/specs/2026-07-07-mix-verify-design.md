# Mix Verify — design

## Problem

Assembling a track from multiple sources (Suno backbone + demucs vocal
stems + library tracks) via hand-built `ffmpeg` graphs repeatedly shipped
"каша" because success was asserted from the **wrong** metric
(`volumedetect` mean/max dB) instead of musical correctness. Concrete
failures that slipped through:

- **`ffprobe` duration lie** — streamed Suno mp3s report 223 s by
  bitrate-estimate while the real decoded length is 133 s.
- **BPM-detector lie** — `librosa.beat.beat_track` quantizes to a fixed
  grid (everything came back "129.2 BPM"), hiding real tempo mismatch.
- **Wrong tempo ratio** — layers stretched by an unverified ratio drift
  out of tempo.
- **Phase / downbeat drift** — layers placed on round-second offsets, not
  on the beat grid → flanging / comb filtering.
- **Vocal masking** — bed and vocal at equal level in the same frequency
  band → "где вокал?!" (vocal buried, inaudible).
- **Level jumps / clipping / silence** between segments.
- **Low-end holes** — techno mix keeps playing, but kick/bass disappears
  for several seconds and the section feels empty.
- **Stereo / mono failure** — severe L/R imbalance or negative channel
  correlation that collapses badly on club mono systems.

## Goal

A verifier that reads the **build plan** (not just the finished file),
runs a battery of checks, and returns a structured PASS/WARN/FAIL report
with the actual measured number and its threshold for each check, plus a
non-zero exit on any FAIL — so delivery can be gated on it.

## Approach

**Manifest-driven.** The build plan is a JSON manifest and the single
source of truth: the `ffmpeg` command is generated *from* it, and the
verifier reads the *same* manifest, so what is verified is exactly what
was rendered.

Rejected alternative: a post-file-only analyzer (extend the existing
`app/audio/render/diagnostics.py`). It cannot catch BPM mismatch, phase
drift, or vocal masking because those require knowing which layer is
which, its declared tempo ratio, and where it was placed.

## Manifest schema

```json
{
  "output": "mix.mp3",
  "backbone": { "source": "backbone.wav", "bpm": 124.53, "bed": true },
  "layers": [
    { "source": "tokyo_vocals.wav", "role": "vocal",
      "src_trim": [15.7, 64.0], "tempo_ratio": 1.00024,
      "place_at": 0.0, "gain": 1.05 }
  ]
}
```

`role` ∈ `{vocal, bed}`. `src_trim` = `[start_s, end_s]` in the source.
`tempo_ratio` = rubberband tempo applied. `place_at` = start offset on the
final timeline. `gain` = linear volume multiplier.

## Checks

Each check is a pure function of the manifest + pre-computed measurements
and returns `CheckResult(name, status, message, detail)` where status ∈
`{PASS, WARN, FAIL}`. Thresholds live in one config object.

Pre-render (source files + manifest):

1. **honest_duration** — decode by sample count; FAIL any source where
   `ffprobe` bitrate-estimate diverges > 2 % from the decoded length.
2. **bpm_reliability** — onset-autocorrelation BPM (never `beat_track`);
   WARN on low autocorrelation-peak confidence or a suspiciously
   quantized value.
3. **tempo_ratio_sanity** — `source_bpm × tempo_ratio` must land within
   ±1 BPM of the backbone BPM; else FAIL.
4. **phase_alignment** — detect each layer's beat grid; the placed
   downbeats must fall within a fraction of a beat (default 0.15) of the
   backbone grid. Reported as **approximate** (no real beatgrid/deck).
5. **source_trim_bounds** — layer trims must be inside the decoded source
   duration; catches silent tails and out-of-range ffmpeg trims.
6. **boundary_alignment** — layer starts/ends should land on the backbone
   beat grid and near 4-beat bars.
7. **timeline** — from the manifest: vocal-on-vocal overlap (one vocal at
   a time), and layers that overrun the bed.

Post-render (finished output):

8. **output_duration** — decoded output length must match the expected
   timeline end; catches truncation and long unintended tails.
9. **vocal_masking** — per vocal window, ratio of vocal-band
   (200 Hz–4 kHz) energy of the isolated vocal layer vs the bed in the
   same window; below threshold → FAIL "vocal buried".
10. **level_jumps** — RMS jump > N dB at segment boundaries.
11. **clipping** — `volumedetect` peak or decoded sample peak ≥ −0.1 dBFS,
    or clipped samples are present.
12. **dropouts** — near-silent windows not declared in the plan.
13. **loudness_consistency** — integrated LUFS per segment via ffmpeg
    `ebur128`; FAIL segments > N LU apart.
14. **low_band_holes** — sustained kick/bass-band dropouts even when the
    full-band signal is not silent.
15. **stereo_balance** — L/R RMS imbalance and negative stereo correlation
    checks for club/mono compatibility.

## Units

- `manifest.py` — dataclasses + JSON load/validate.
- `analysis.py` — pure measurement primitives (honest decode, onset BPM +
  confidence, beat grid, RMS series, band energy, segment LUFS). No check
  logic.
- `checks.py` — one function per check; pure over (manifest, measurements,
  config).
- `report.py` — aggregate, format (text + JSON), compute exit code.
- `__main__.py` — CLI glue: load manifest → measure → run checks → report.

Location: `scripts/verify_mix/` (standalone, CLI-runnable). Not wired into
the MCP tool surface — YAGNI; can be promoted to a `render_verify` MCP
tool later.

## Dependencies

`numpy`, `librosa`, `scipy` (already in `[audio]` extra), `ffmpeg` (external).
Segment LUFS via ffmpeg `ebur128` — no extra Python dep. Everything
degrades gracefully if a source stem is absent (that check → WARN, not a
crash).

## Testing

Synthetic fixtures (sine tones, click tracks at known BPM, a loud bed
over a quiet vocal) assert each check **both** fires on a bad input and
passes on a good one.
