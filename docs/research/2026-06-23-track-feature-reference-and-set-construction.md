# Track Feature Reference + Set-Construction Playbook (v2)

> Research date: 2026-06-23. Maps **every** `track_audio_features_computed`
> column to its DJ-set-construction meaning, grades each feature's
> **discriminative signal on *this* library** (measured p10/p50/p90 over the
> live ~24k-track DB), and distils an advanced, data-grounded set-construction
> playbook. Companion to [audio-schema.md](../audio-schema.md),
> [transition-scoring.md](../transition-scoring.md), [domain-glossary.md](../domain-glossary.md).
>
> **Why a signal-quality grade?** The library is acoustically homogeneous
> (acid/industrial/detroit/dub techno, 122–130 BPM core). Many features that
> are powerful *in theory* have a **tiny real spread here** and cannot separate
> tracks — this is the same root cause that makes the mood classifier degenerate
> (see the catch-all-penalty investigation). Curate on the features that
> actually vary on this data.

## Signal-quality legend

| Grade | Meaning | Use it for |
|---|---|---|
| **strong** | wide real spread, reliable | primary selection / arc / scoring axis |
| **usable** | moderate spread or reliable-when-present | secondary axis, clustering, technique routing |
| **weak (low spread)** | near-constant on this library | do NOT filter/rank on it here; comparative-at-extremes only |
| **null/miscal** | mostly NULL at L2, or unit-scale mismatch, or unused | bring set to L5 before trusting; don't filter `__gte/__lte` on L2 |

## Per-feature reference

### Tempo & rhythm

| Feature | Measures | DJ use | Signal here |
|---|---|---|---|
| `bpm` | Tempo via onset-autocorrelation + parabolic interpolation (`min_bpm` guard), half/double-aware | **Primary** ordering + filter axis; 2–3 BPM-step arc; drives `S_bpm` (σ=10: Δ5→0.88, Δ8→0.73, Δ10→hard-reject) + 50% of drums stem | **strong** |
| `bpm_stability` | `1 − 2·CV` of median-filtered inter-beat intervals; 1=metronomic | ×-multiplier (floor 0.7) on `S_bpm`/drum-lock; prefer high for long blends | **weak** (p10/50/90 0.92/0.94/0.96 — everyone metronomic) |
| `variable_tempo` | bool: filtered-IBI CV > 0.15; flat −0.15 on `S_bpm`, never hard-rejects | curation flag for non-grid material | **usable** (rare True after IBI filter — investigate, don't auto-reject) |
| `bpm_confidence` | 0.7·peak-strength + 0.3·peak-dominance | trust dial; attenuates `S_bpm` below floor 0.3 | **null/miscal** — mostly NULL at L2; **never `bpm_confidence__gte` on an L2 crate** (NULL fails `>=`, silently empties) |
| `onset_rate` | BEAT-peak events/sec (sub-beat peaks pruned) — tempo-linked, **not** hi-hat busyness | 15% of drums stem (proximity) | **weak** (1.75/2.03/2.18 — co-varies with the narrow BPM band) |
| `pulse_clarity` | onset-autocorr peak / lag-0 energy | beatmatch-difficulty / floor-lock; flags rare washy outliers | **weak** (0.78/0.89/0.93) |
| `kick_prominence` | onset-weighted fraction of energy <200 Hz (kick+sub proxy, **not** a kick detector) | 25% of drums stem; low-end-clash cue → DRUM_CUT/DRUM_SWAP vs overlap | **usable** (0.74/0.86/0.95 — compressed but ranks within the kick-forward core) |
| `hp_ratio` | `sqrt(harmonic/percussive)` via HPSS; unbounded | drives adaptive swap length + picker routing (drum-swap vs harmonic-sustain) | **usable** (1.67/2.24/2.90 — decent tonal-vs-drums axis) |
| `dominant_phrase_bars` | phrase length 8/16/32 by chroma-delta argmax (assumes 4/4) | match between A/B so a 32-bar blend stays aligned; mix in on a phrase boundary | **usable** (detects LENGTH, not absolute START) |
| `phrase_boundaries_ms` | phrase-boundary timestamps within the 60s clip | mix-in/out anchors; recipe bars span boundary-to-boundary | **usable** (only the analyzed window; `dj_cue_points` empty → this + `track_sections` are the only mix-point source) |
| `tempogram_ratio_vector` | 10 onset-autocorr strengths at BPM ratios 0.5..5.0 | metric-feel fingerprint | **weak** (0.5×/2× harmonics near-universal in clean 4/4; only 1.5×/2.5×/3.5× swing discriminates) |
| `bpm_histogram_first_peak_weight` / `_second_peak_bpm` / `_second_peak_weight` | essentia beat-interval histogram peaks (needs ≥4 intervals) | second read on steadiness; half/double-time scout | **null/miscal** (essentia-gated, mostly NULL; redundant with `bpm_stability`) |

### Loudness & dynamics

| Feature | Measures | DJ use | Signal here |
|---|---|---|---|
| `integrated_lufs` | ITU-R BS.1770-4, gated whole-track program loudness | **THE energy-arc axis** + input to `S_energy` (Gauss, preferred **+0.5 LUFS** rise) + **hard-reject** (>6 LUFS gap). Park loudest at ~0.6–0.7 of the set; keep steps <2–3 LU | **strong** (−14.3/−12.3/−10.7 — hot-mastered; relative-within-crate ranker) |
| `short_term_lufs_mean` | mean of 3 s sliding loudness | section-level felt loudness; `(short_term − integrated)` = back-loaded vs uniform; match at the **mix section** | **usable** |
| `momentary_max` | max 400 ms loudness (usually the drop) | set-apex identifier; `(momentary_max − integrated)` = dynamics; overlap-headroom warning | **usable** |
| `rms_dbfs` | flat-weighted RMS (over-counts sub) | crest-factor denominator + sub-heaviness tell; **never gain-match on it** | **usable** |
| `true_peak_db` | 4×-oversampled inter-sample peak (dBTP) | clipping/headroom — trim hot tracks. **p50 +0.49, p90 +1.45** (hot masters; the `>0` audit warning fires on ~75% — it's a warning, not a fail) | **null/miscal** at L2 — don't `true_peak_db__lte` an L2 crate |
| `crest_factor_db` | `true_peak − rms` = peak-to-average punch | within-set variety cue; `S_energy` −0.10 only when `|diff|>10 dB` (config) | **weak** (8.7/10.3/12.2 — ~3.5 dB spread, well inside the 10 dB gate → penalty almost never fires) |
| `loudness_range_lu` | simplified LRA (10th–95th pct of short-term, −70 gate only) | macro-dynamics: wide=quiet-intro→drop tension; narrow=relentless roller. `S_energy` −0.10 only when `|diff|>8 LU` | **usable** (3.0/6.1/10.4 — real arrangement-shape axis; 8 LU gate is loose so it rarely penalises) |

### Energy (per-track, max-normalized — NOT loudness)

| Feature | Measures | DJ use | Signal here |
|---|---|---|---|
| `energy_mean` | mean per-frame **power**, max-normalized per track | best in-library **perceptual-intensity** proxy for RANKING within a slot + planning a 1–10 arc level. **NOT cross-track comparable as loudness** (use `integrated_lufs` for the real step) | **usable** (0.22/0.32/0.44 — compressed but works) |
| `energy_max` | ≈1.0 for every non-silent track (normalization artifact) | **ignore** — zero cross-track info | **null/miscal** |
| `energy_std` | std of normalized frame energy = within-track eventfulness | low=steady roller (long blends), high=built-in build/drop | **weak** (0.21/0.25/0.29) |
| `energy_slope` | OLS slope of frame energy over the 60s clip (sign + rough magnitude) | per-track build-vs-fade: positive builders on the way up, negative faders on descent; `S_energy` +0.05 for same-sign neighbours | **usable** (use the sign) |
| `energy_low` | relative power 60–250 Hz (kick body + bass fundamental) | half of bass-stem proximity; **#1 mud/clash band** → bass-swap not overlap | **usable** (0.23/0.40/0.61 — most usable energy band) |
| `energy_sub` | relative power 20–60 Hz (felt sub) | sub weight for peak impact + clash band (relative, sums ~1) | **usable** |
| `energy_lowmid/mid/highmid/high` (+ `*_ratio`) | relative power 250-500 / 500-2k / 2-4k / 4-8k Hz; ratios partition to 1.0 | cross-track **brightness/tonal-balance fingerprint**; `highmid` carries 303-resonance (why the vocal proxy uses lowmid+mid, not highmid) | **usable** (the `*_ratio` set is the cross-track-comparable spectral shape; extended — not read by the live crossfade engine) |

### Spectral & timbral

| Feature | Measures | DJ use | Signal here |
|---|---|---|---|
| `spectral_centroid_hz` | amplitude-weighted mean frequency (brightness) | **the single best spectral discriminator here**; 40% of vocals/timbral stem + picker vocal gate (>2200 Hz). Use as a **second arc** (dark→bright→dark) | **strong** (1533/2181/2853) |
| `spectral_rolloff_85` / `_95` | freq below which 85/95% of magnitude sits | corroborating brightness check (don't double-count with centroid) | **usable** |
| `spectral_flatness` | 0=tonal, 1=noise | read **before** trusting `S_harmonic`: low→key matters, high→mix on groove | **usable** (0.20/0.30/0.39 — melodic-vs-industrial axis) |
| `spectral_flux_mean` / `_std` | frame-to-frame magnitude change / its std | eventfulness → transition LENGTH (low=long blend, high=short cut); std=internal drama | **weak** (0.075/0.106/0.143 ; 0.053/0.072/0.090 — tiny + stitched-seam-inflated) |
| `spectral_slope` | dB/octave spectral tilt | tonal-balance consistency check — big mismatch is the hidden cause of an "off" blend even with BPM/key/LUFS matched | **weak** (limiting flattens it; techno clusters tight) |
| `spectral_contrast` | mean peak−valley dB over 6 octave bands | 10% of harmonic stem (`1−|d|/15`); harmonic clarity | **weak** (18.1/19.5/21.7 — ~3.6 dB spread → near-zero discrimination in `S_harmonic` here) |
| `mfcc_vector` (13) | timbral fingerprint (librosa, L3+) | 20% of harmonic stem (cosine); among the strongest cues for **where** DJs blend | **null/miscal** at L2 → harmonic stem silently collapses onto Camelot. **L5 the set.** |
| `spectral_complexity_mean` | mean spectral-peak count (essentia, L3+) | arrangement density — two dense tracks overlapped = mush (favour cut/stem-swap) | **null/miscal** (essentia-gated, NULL on L2 majority; not read by crossfade engine) |

### Harmonic & tonal

| Feature | Measures | DJ use | Signal here |
|---|---|---|---|
| `key_code` | 0–23 Camelot **slot** (`//2+1`=wheel pos, `%2`=mode); NOT pitchclass×mode | Camelot distance → `S_harmonic` (base {0:1.0,1:0.9,2:0.6,3:0.3,4:0.1}) + bass stem; **distance ≥5 = HARD REJECT**. L5 can shift it — re-score after L5 | **usable** but **treat as soft for percussive techno** (see atonality) |
| `key_confidence` | chromagram template-match strength | now **gates the Camelot hard-reject** (with `atonality`): the ≥5 reject only fires when both tracks have `key_confidence >= hard_reject_key_confidence_floor` (0.5) — fixed 2026-06-23 | **usable** as a gate (still NULL-at-L2-prone — don't filter on it there) |
| `atonality` | bool = normalized `chroma_entropy > 0.92` | "relax the key rules" — atonal tracks are universal connectors. **98.7% of our library is atonal**; now **wired**: an atonal track on either side skips the Camelot hard-reject | **usable** as a gate |
| `chroma_entropy` | Shannon entropy of 12-bin chroma, **normalized [0,1]** (not raw bits) | harmonic busyness; 30% of vocals stem via `1−|d|` (scale fixed 2026-06-23) | **null/miscal** (0.96/0.98/0.99 near-constant — weak discriminator regardless) |
| `hnr_db` | harmonic-to-noise ratio (dB) | multiplies the Camelot base in `S_harmonic` (−30..0 dB → 0.5..1.0) — **the ONLY live key-relaxation mechanism** (soft only, never the hard reject) | **usable** (−2.3/1.2/3.2 — low, percussive) |
| `tonnetz_vector` (6) | tonal-centroid (Harte) over fifth/3rd circles (L3+) | 20% of harmonic stem (cosine); continuous harmonic distance beyond discrete key | **null/miscal** at L2 → Camelot share of `S_harmonic` rises toward ~80–100%; meaningless for atonal tracks |
| `dissonance_mean` | Plomp-Levelt sensory roughness 0–1 (essentia) | flat −0.15 on `S_harmonic` when **both** >0.4 | **null/miscal** (≈0.49/0.50/0.50 near-constant → penalty fires ~uniformly = a constant offset, zero discrimination here) |

### Classification (essentia-derived; mostly NULL at L2)

| Feature | Measures | DJ use | Signal here |
|---|---|---|---|
| `danceability` | essentia DFA self-similarity, **unbounded ~0–3 (NOT 0–1)** | groove-tightness/floor-lock axis distinct from `energy_mean`; **never min-max vs 0–1 features without rescaling** | **null/miscal** (essentia-gated; good spread when present) |
| `dynamic_complexity` | essentia loudness-domain deviation, **~0–10 (NOT 0–1)** | loudness-domain twin of `energy_std`: low=wall, high=builds/drops | **null/miscal** (rescale before mixing with 0–1 features; NULL on L2) |
| `pitch_salience_mean` | essentia harmonic-peak energy ratio 0–1 | **sustained-pitched-content PROXY, NOT vocal detection**; drives picker (`>0.55 AND centroid>2200 AND lowmid+mid>0.40` rejects acid-303 false positives) + 30% of vocals stem | **null/miscal** (essentia-gated; 0.68/0.79/0.88 when present) |
| `mood` / `mood_confidence` | rule-based 15-subgenre classifier (catch-all driving/hypnotic penalized) | **degenerate/low-confidence on this homogeneous library** — curate FEATURE-FIRST, use `mood` only as a loose hint | **null/miscal** (median confidence ≈0.05) |

## Set-construction playbook v2 (advanced, data-grounded)

1. **Select before the booth, feature-first.** Pack a per-gig crate of ~25–40 from the 24k library, not the whole thing. Because the mood classifier is degenerate here, curate on features with real spread: `integrated_lufs`, `spectral_centroid_hz` (best discriminator), `energy_mean`, `bpm`, `key_code`, `hp_ratio`. **Ignore as selection axes**: `dissonance_mean` (~0.50), `spectral_contrast` (~3.6 dB), `spectral_flux`, `bpm_stability` (0.92–0.96), `onset_rate` — they can't separate this library.
2. **Give each track a job, not just a vibe.** Tag crate tracks as banger / tool / bridge / breather / statement. Tools = long drumless intro/outro (`track_sections` + `phrase_boundaries_ms`), steady (`energy_std` low). Statements = highest `momentary_max` + positive `energy_slope`. Bridges = atonal / low-`key_confidence` percussive connectors. Build FROM the roles.
3. **Build the arc on `integrated_lufs`, not `energy_mean`, not BPM.** `energy_mean` is per-track max-normalized → cannot express a cross-track loudness step. Use `energy_mean`/`danceability`/`energy_low` to RANK intensity within a slot, but verify the track-to-track step on `integrated_lufs` (keep <2–3 LU; engine prefers +0.5 LU).
4. **Shape a sawtooth, peak at ~0.6–0.7.** Global peak two-thirds through (`fitness.py ideal_peak_pos=0.7`), 1–2 smaller earlier rises, deliberate valleys (drop 2–3 levels after a peak). The GA maximises *pairwise* quality and scatters energy if left alone — **impose the arc by hand-ordering/template, then let `set_version_build` re-score**. A clean-arc order a few points below GA-optimal is the intentional contrast.
5. **Exploit `energy_slope` for a self-driving arc.** Positive-slope builders on the way up / before peaks; negative faders on the descent; flat rollers as sustainers. `S_energy` rewards same-sign neighbours (+0.05).
6. **Use brightness as a second arc** — `spectral_centroid_hz` is the one spectral feature with wide spread here. Open dark (dub/detroit), creep brighter into the peak (acid/peak-time), darken for the comedown. Gives the homogeneous library a perceivable second dimension when loudness alone is too compressed.
7. **Manage low end as a clash problem.** `energy_sub` + `energy_low` feed bass-stem **similarity** (not a clash detector) — two tracks both high-and-similar in sub are exactly what muds when blended full-range. The clash call + bass-swap are MANUAL; use `kick_prominence` mismatch as the cue to DRUM_CUT/DRUM_SWAP.
8. **Key is a soft preference for percussive techno.** Plan smooth blends within Camelot distance ≤1; save bigger key moves for after a breakdown. **Trust key only when `key_confidence` high and `atonality` False** — on sparse/atonal tracks the ≥5 Camelot hard-reject can be a FALSE reject (the engine does NOT relax it for low confidence/atonality; only `hnr_db` down-weights the SOFT score). Route atonal/percussive pairs on groove and let the picker pick DRUM_SWAP/DRUM_CUT/FADE.
9. **Set transition length by eventfulness — but know the signal is weak here.** Theory: low flux/complexity → long 32-bar blend, high → short cut. But flux/contrast have tiny spread and complexity is NULL at L2. Lean on `hp_ratio` (real spread) + `track_sections`: percussion-led low-`hp_ratio` tracks tolerate fast cuts; tonal high-`hp_ratio` need longer gentle blends.
10. **Match phrase structure, not just beats.** Match `dominant_phrase_bars` and mix in on a phrase boundary. Caveat: `dj_beatgrids` ~0.1% coverage, `dj_cue_points` empty → true downbeat falls back to t=0 (fine for intro-on-1 techno).
11. **Know the actual runtime weights.** The documented 6-component `DEFAULT_WEIGHTS` apply only on the **no-intent** path. The set-build path **sets an intent**, so scoring uses `INTENT_WEIGHT_MODIFIERS` (see [transition-scoring.md](../transition-scoring.md#effective-runtime-weights)): e.g. `RAMP_UP` = energy 0.30 / harmonics 0.25 / **drums 0.05** — during builds, loudness-flow + harmonic continuity drive the score, NOT kick lock.
12. **Bring set tracks to L5 before finalizing.** `mfcc_vector`, `tonnetz_vector` (20%+20% of `S_harmonic`), `pitch_salience`, `danceability`, `dynamic_complexity`, `true_peak`/`crest` are NULL on the L2 majority — at L2 the harmonic stem collapses onto Camelot alone and the picker can't see vocal/melodic content. Download + L5-reanalyze the set in batches of 3–5 (under the 120s MCP timeout), rebuild `set_version`, re-read transitions. L5 can shift `key_code`.
13. **Recorded mix vs club.** Podcast/recorded → prioritise internal loudness consistency (streaming normalizes to ~−14 LUFS anyway) + clean transitions, avoid too many full peaks. Live club → conservative headroom (trim true-peak-hot tracks), stay responsive over a fixed setlist.

## Known code/scale quirks surfaced by this audit

Status legend: ✅ fixed · ⚠️ documented/low-impact · 🔭 Phase-2 (flagged, not applied).

- ✅ **`chroma_entropy /3.0` scale bug** (`neural_mix.score_vocal_compat` + `bulk_scorer`): the feature is normalized to [0,1] but the proximity divided by 3.0 (the old raw-bits scale), so the term could never drop below 0.667. Fixed → `/1.0` (golden snapshots regenerated). Near-zero practical effect on *this* library (chroma is near-constant) but correct in general.
- ✅ **Camelot is now key-reliability-aware — both the hard reject AND the soft score** (`key_confidence` + `atonality`). The distance ≥5 **hard reject** fires only when BOTH tracks are tonal (`not atonality`) and confident (`key_confidence >= hard_reject_key_confidence_floor`, default 0.5). The **soft** Camelot term in `S_bass`/`S_harmonic` falls back to neutral 0.5 (same as missing-key) when either side is unreliable, so a meaningless key distance no longer drags atonal/percussive pairs. On a 98.7%-atonal library the old unconditional gate false-rejected and the old soft term mis-scored these pairs. Reliability is a single shared notion (`hard_constraints.key_reliable` scalar / `bulk_scorer._key_reliable_mask` vector, parity-tested); zero impact on golden fixtures. 🔭 Remaining (lower-priority): a *continuous* per-subgenre Camelot weight instead of the binary reliable/neutral gate.
- ✅ **`beat_loudness_band_ratio` populates at L5**: the `beats_loudness` analyzer ran on the full-track clip while `beat` produces beat_times on the 60s stitched clip → essentia got mismatched positions → NULL library-wide. Pinned `clip_duration_s=60.0` (verified: now `[0.886, 0.026, …]`). Only NEW L5 analyses populate it; existing L5 rows need a re-L5 backfill; the scorer renormalises gracefully when NULL.
- ✅ **Camelot tables unified** to a single source of truth: `weights.CAMELOT_HARMONIC_BASE` / `CAMELOT_BASS_BASE` are now imported by both `neural_mix.py` (scalar) and `bulk_scorer.py` (vectorised), so the two paths can never drift. Zero behaviour change (golden diff empty). The old `CAMELOT_BASE_SCORES` + `config.transition.weight_*` + `CREST/LRA_DIFF_PENALTY_THRESHOLD` (4.0/5.0) remain comment-marked reference-only (kept because tests pin them).
- ⚠️ **`dissonance_mean` penalty (`>0.4` both)** fires near-uniformly (data ≈0.50) → a constant offset, no discrimination here. Magic-number; low practical impact (ranking-neutral).
- ⚠️ **`true_peak_db > 0` clipping audit** flags ~75% of the (hot-mastered) library — a warning, not a fail; defensible but noisy.
- **`true_peak_db > 0` clipping audit** flags ~75% of the (hot-mastered) library — a warning, not a fail; defensible but noisy.

## Citations

- DJ.Studio — Anatomy of a great DJ mix; Camelot wheel: <https://dj.studio/blog/anatomy-great-dj-mix-structure-energy-flow-transition-logic>
- SetFlow — DJ set energy flow (1–10 journey models): <https://www.setflow.app/blog/dj-set-energy-flow>
- Mixgraph — set-planning + energy-flow guides: <https://www.mixgraph.io/learn/dj-set-planning-guide>
- Mixed In Key — harmonic mixing guide (Camelot, +7, percussive tolerance): <https://mixedinkey.com/harmonic-mixing-guide/>
- Native Instruments — harmonic-mixing rules & how to break them: <https://blog.native-instruments.com/harmonic-mixing-rules-and-how-to-break-them/>
- Bittner et al., ISMIR 2016 (Spotify) — Automatic Playlist Sequencing & Transitions (key-clash 0%, beat-misalignment 15%, loudness cost, timbre predictor): <https://rachelbittner.weebly.com/uploads/3/2/1/8/32182799/bittner_ismir-playlist_2017.pdf>
- Zehren et al., ISMIR 2020 — Automatic Detection of Cue Points for DJ Mixing: <https://arxiv.org/pdf/2007.08411>
- EBU R128 / TECH 3342 (LUFS, LRA), ITU-R BS.1770-4 (K-weighting, true peak)
- Code: `app/domain/transition/{weights,intent,neural_mix,scorer,components/energy,hard_constraints,picker,bulk_scorer}.py`, `app/audio/analyzers/{bpm,key}.py`, measured library distributions (this audit).
