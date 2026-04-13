"""Programmatic DJ mixer with EQ-based transitions aligned to beatgrid.

Reads MP3 tracks, applies transition recipes (bass swap, EQ blend,
filter sweep, echo out) using scipy butterworth filters, and renders
a single mixed MP3 with transitions on phrase boundaries.

Usage:
    python scripts/dj_mix_render.py --input-dir generated-sets/acid-set --output mix.mp3
    python scripts/dj_mix_render.py --input-dir generated-sets/acid-set --crossfade-bars 16
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mixer")

SR = 44100  # sample rate


# ── EQ Filters ───────────────────────────────────────────────


def _butter_lowpass(cutoff: float, order: int = 4) -> np.ndarray:
    return butter(order, cutoff / (SR / 2), btype="low", output="sos")


def _butter_highpass(cutoff: float, order: int = 4) -> np.ndarray:
    return butter(order, cutoff / (SR / 2), btype="high", output="sos")


def _butter_bandpass(low: float, high: float, order: int = 4) -> np.ndarray:
    return butter(order, [low / (SR / 2), high / (SR / 2)], btype="band", output="sos")


def split_3band(audio: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split audio into low (<200Hz), mid (200-4000Hz), high (>4000Hz)."""
    low = sosfilt(_butter_lowpass(200), audio, axis=0)
    high = sosfilt(_butter_highpass(4000), audio, axis=0)
    mid = audio - low - high
    return low, mid, high


def apply_hpf_sweep(audio: np.ndarray, start_freq: float, end_freq: float) -> np.ndarray:
    """Apply a high-pass filter sweep across the audio."""
    n = len(audio)
    chunk_size = n // 20  # 20 steps
    result = np.zeros_like(audio)
    for i in range(20):
        start = i * chunk_size
        end = min((i + 1) * chunk_size, n)
        freq = start_freq + (end_freq - start_freq) * (i / 19)
        freq = max(20, min(freq, SR / 2 - 100))
        sos = _butter_highpass(freq, order=2)
        result[start:end] = sosfilt(sos, audio[start:end], axis=0)
    return result


# ── Beatgrid Helpers ─────────────────────────────────────────


def estimate_bpm_from_duration(duration_s: float) -> float:
    """Rough BPM estimate — works for our tracks since we know they're ~128 BPM."""
    return 128.0  # All our acid tracks are 128 BPM


def bars_to_samples(bars: int, bpm: float) -> int:
    """Convert bar count to sample count."""
    seconds_per_bar = (60.0 / bpm) * 4  # 4 beats per bar
    return int(seconds_per_bar * bars * SR)


def find_phrase_boundary(audio: np.ndarray, target_pos: int, bpm: float) -> int:
    """Snap position to nearest 4-bar phrase boundary."""
    bar_samples = bars_to_samples(1, bpm)
    phrase_samples = bar_samples * 4  # 4-bar phrase
    phrase_idx = round(target_pos / phrase_samples)
    return int(phrase_idx * phrase_samples)


# ── Transition Renderers ─────────────────────────────────────


@dataclass
class TransitionResult:
    """Result of rendering a transition between two tracks."""

    audio: np.ndarray  # The blended transition region
    a_end: int  # Where to cut track A (sample index from start of A)
    b_start: int  # Where track B starts contributing (sample index from start of B)
    type_name: str


def render_bass_swap(
    track_a: np.ndarray,
    track_b: np.ndarray,
    overlap_bars: int,
    bpm: float,
    swap_bar: int | None = None,
) -> TransitionResult:
    """Bass swap transition: crossfade mids/highs, swap bass at a specific bar."""
    overlap_samples = bars_to_samples(overlap_bars, bpm)

    # Take the last N bars of A and first N bars of B
    a_region = track_a[-overlap_samples:]
    b_region = track_b[:overlap_samples]

    # Pad if needed
    if len(a_region) < overlap_samples:
        a_region = np.pad(a_region, ((overlap_samples - len(a_region), 0), (0, 0)))
    if len(b_region) < overlap_samples:
        b_region = np.pad(b_region, ((0, overlap_samples - len(b_region)), (0, 0)))

    # Split into bands
    a_low, a_mid, a_high = split_3band(a_region)
    b_low, b_mid, b_high = split_3band(b_region)

    # Bass swap point (default: halfway, or at specified bar)
    if swap_bar is None:
        swap_bar = overlap_bars // 2
    swap_sample = bars_to_samples(swap_bar, bpm)
    swap_sample = min(swap_sample, overlap_samples)

    # Crossfade envelope
    n = overlap_samples
    fade = np.linspace(0, 1, n).reshape(-1, 1)

    # Bass: hard swap at swap point
    low_mix = np.concatenate(
        [
            a_low[:swap_sample],
            b_low[swap_sample:],
        ]
    )

    # Mids: gradual crossfade
    mid_mix = a_mid * (1 - fade) + b_mid * fade

    # Highs: gradual crossfade (slightly faster)
    high_fade = np.clip(fade * 1.3, 0, 1)
    high_mix = a_high * (1 - high_fade) + b_high * high_fade

    blended = low_mix + mid_mix + high_mix

    return TransitionResult(
        audio=blended,
        a_end=len(track_a) - overlap_samples,
        b_start=overlap_samples,
        type_name=f"BASS_SWAP ({overlap_bars} bars)",
    )


def render_eq_blend(
    track_a: np.ndarray,
    track_b: np.ndarray,
    overlap_bars: int,
    bpm: float,
) -> TransitionResult:
    """EQ blend: gradually transfer each band from A to B."""
    overlap_samples = bars_to_samples(overlap_bars, bpm)

    a_region = track_a[-overlap_samples:]
    b_region = track_b[:overlap_samples]

    if len(a_region) < overlap_samples:
        a_region = np.pad(a_region, ((overlap_samples - len(a_region), 0), (0, 0)))
    if len(b_region) < overlap_samples:
        b_region = np.pad(b_region, ((0, overlap_samples - len(b_region)), (0, 0)))

    a_low, a_mid, a_high = split_3band(a_region)
    b_low, b_mid, b_high = split_3band(b_region)

    n = overlap_samples
    # Staggered fades: high first, then mid, then low
    high_fade = np.clip(np.linspace(-0.2, 1.2, n), 0, 1).reshape(-1, 1)
    mid_fade = np.clip(np.linspace(-0.1, 1.1, n), 0, 1).reshape(-1, 1)
    low_fade = np.linspace(0, 1, n).reshape(-1, 1)

    blended = (
        a_low * (1 - low_fade)
        + b_low * low_fade
        + a_mid * (1 - mid_fade)
        + b_mid * mid_fade
        + a_high * (1 - high_fade)
        + b_high * high_fade
    )

    return TransitionResult(
        audio=blended,
        a_end=len(track_a) - overlap_samples,
        b_start=overlap_samples,
        type_name=f"EQ_BLEND ({overlap_bars} bars)",
    )


def render_filter_sweep(
    track_a: np.ndarray,
    track_b: np.ndarray,
    overlap_bars: int,
    bpm: float,
) -> TransitionResult:
    """Filter sweep: HPF sweep on A while fading in B."""
    overlap_samples = bars_to_samples(overlap_bars, bpm)

    a_region = track_a[-overlap_samples:]
    b_region = track_b[:overlap_samples]

    if len(a_region) < overlap_samples:
        a_region = np.pad(a_region, ((overlap_samples - len(a_region), 0), (0, 0)))
    if len(b_region) < overlap_samples:
        b_region = np.pad(b_region, ((0, overlap_samples - len(b_region)), (0, 0)))

    # HPF sweep on A: 20Hz → 8000Hz
    a_swept = apply_hpf_sweep(a_region, 20, 8000)

    # Volume fade
    n = overlap_samples
    fade_out = np.linspace(1, 0, n).reshape(-1, 1)
    fade_in = np.linspace(0, 1, n).reshape(-1, 1)

    blended = a_swept * fade_out + b_region * fade_in

    return TransitionResult(
        audio=blended,
        a_end=len(track_a) - overlap_samples,
        b_start=overlap_samples,
        type_name=f"FILTER_SWEEP ({overlap_bars} bars)",
    )


def render_echo_out(
    track_a: np.ndarray,
    track_b: np.ndarray,
    overlap_bars: int,
    bpm: float,
) -> TransitionResult:
    """Echo out: fade A with reverb tail, bring in B clean."""
    overlap_samples = bars_to_samples(overlap_bars, bpm)

    a_region = track_a[-overlap_samples:]
    b_region = track_b[:overlap_samples]

    if len(a_region) < overlap_samples:
        a_region = np.pad(a_region, ((overlap_samples - len(a_region), 0), (0, 0)))
    if len(b_region) < overlap_samples:
        b_region = np.pad(b_region, ((0, overlap_samples - len(b_region)), (0, 0)))

    n = overlap_samples
    # Exponential fade out for echo effect
    fade_out = np.exp(-np.linspace(0, 5, n)).reshape(-1, 1)
    fade_in = np.linspace(0, 1, n).reshape(-1, 1)

    # Simple delay echo on A (add delayed copy at -6dB)
    delay_samples = bars_to_samples(1, bpm) // 2  # half-bar delay
    a_echo = np.zeros_like(a_region)
    if delay_samples < n:
        a_echo[delay_samples:] = a_region[:-delay_samples] * 0.4

    blended = (a_region + a_echo) * fade_out + b_region * fade_in

    return TransitionResult(
        audio=blended,
        a_end=len(track_a) - overlap_samples,
        b_start=overlap_samples,
        type_name=f"ECHO_OUT ({overlap_bars} bars)",
    )


def render_cut(
    track_a: np.ndarray,
    track_b: np.ndarray,
    bpm: float,
) -> TransitionResult:
    """Hard cut with tiny crossfade to avoid click."""
    # 50ms micro-crossfade to avoid click artifacts
    xfade = int(0.05 * SR)
    a_tail = track_a[-xfade:]
    b_head = track_b[:xfade]

    fade = np.linspace(0, 1, xfade).reshape(-1, 1)
    blended = a_tail * (1 - fade) + b_head * fade

    return TransitionResult(
        audio=blended,
        a_end=len(track_a) - xfade,
        b_start=xfade,
        type_name="CUT",
    )


# ── Transition Selection ─────────────────────────────────────


def select_transition(
    score_overall: float,
    overlap_bars: int,
) -> str:
    """Select transition type based on score."""
    if score_overall >= 0.85:
        return "bass_swap"
    elif score_overall >= 0.70:
        return "eq_blend"
    elif score_overall >= 0.55:
        return "filter_sweep"
    elif score_overall >= 0.40:
        return "echo_out"
    else:
        return "filter_sweep"


def render_transition(
    track_a: np.ndarray,
    track_b: np.ndarray,
    bpm: float,
    transition_type: str,
    overlap_bars: int,
) -> TransitionResult:
    """Dispatch to the appropriate transition renderer."""
    if transition_type == "cut":
        return render_cut(track_a, track_b, bpm)
    elif transition_type == "bass_swap":
        return render_bass_swap(track_a, track_b, overlap_bars, bpm)
    elif transition_type == "eq_blend":
        return render_eq_blend(track_a, track_b, overlap_bars, bpm)
    elif transition_type == "filter_sweep":
        return render_filter_sweep(track_a, track_b, overlap_bars, bpm)
    elif transition_type == "echo_out":
        return render_echo_out(track_a, track_b, overlap_bars, bpm)
    else:
        return render_bass_swap(track_a, track_b, overlap_bars, bpm)


# ── Main Assembler ───────────────────────────────────────────


def load_track(path: Path) -> np.ndarray:
    """Load MP3 as float32 stereo numpy array."""
    data, sr = sf.read(str(path), dtype="float32")
    if sr != SR:
        # Resample would be ideal but for now just use as-is
        log.warning("  Sample rate %d != %d, using as-is", sr, SR)
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    return data


def _load_features_for_files(mp3_files: list[Path]) -> dict[int, TrackFeatures]:
    """Load audio features from Supabase for each file by title matching."""
    import re

    import httpx

    from scripts.build_set_from_db import _load_supabase_creds, _row_to_features

    try:
        sb_url, sb_key = _load_supabase_creds()
    except SystemExit:
        return {}

    headers = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}"}

    fields = (
        "track_id,bpm,bpm_confidence,bpm_stability,variable_tempo,"
        "integrated_lufs,short_term_lufs_mean,loudness_range_lu,crest_factor_db,"
        "energy_mean,energy_slope,"
        "energy_sub,energy_low,energy_lowmid,energy_mid,energy_highmid,energy_high,"
        "spectral_centroid_hz,spectral_rolloff_85,spectral_rolloff_95,"
        "spectral_flatness,spectral_flux_std,"
        "spectral_slope,spectral_contrast,hnr_db,chroma_entropy,"
        "key_code,key_confidence,atonality,"
        "mfcc_vector,onset_rate,pulse_clarity,kick_prominence,hp_ratio,"
        "mood,mood_confidence,analysis_level,"
        "tonnetz_vector,tempogram_ratio_vector,"
        "beat_loudness_band_ratio,danceability,dissonance_mean,"
        "dynamic_complexity,pitch_salience_mean,spectral_complexity_mean"
    )

    # Extract track titles from filenames (remove "01. " prefix and ".mp3" suffix)
    title_map: dict[str, int] = {}
    for idx, f in enumerate(mp3_files):
        name = f.stem
        # Remove leading number prefix like "01. " or "01 "
        clean = re.sub(r"^\d+[\.\s]+", "", name).strip()
        title_map[clean.lower()] = idx

    # Search by mood=acid (our set) — get all acid features
    r = httpx.get(
        f"{sb_url}/rest/v1/track_audio_features_computed?select={fields}"
        "&mood=eq.acid&bpm=not.is.null&integrated_lufs=not.is.null&limit=200",
        headers=headers,
    )
    if r.status_code != 200:
        return {}

    rows = r.json()
    track_ids = [str(row["track_id"]) for row in rows]
    if not track_ids:
        return {}

    # Get titles for these tracks
    titles: dict[int, str] = {}
    for i in range(0, len(track_ids), 50):
        batch = track_ids[i : i + 50]
        r2 = httpx.get(
            f"{sb_url}/rest/v1/tracks?select=id,title&id=in.({','.join(batch)})",
            headers=headers,
        )
        if r2.status_code == 200:
            for t in r2.json():
                titles[t["id"]] = t["title"]

    # Match DB titles to filenames
    result: dict[int, TrackFeatures] = {}
    for row in rows:
        tid = row["track_id"]
        db_title = titles.get(tid, "").lower()
        for file_title, file_idx in title_map.items():
            # Fuzzy match: check if significant part of title matches
            if db_title and (db_title in file_title or file_title in db_title):
                result[file_idx] = _row_to_features(row)
                break

    return result


def assemble_set(
    mp3_files: list[Path],
    bpm: float,
    overlap_bars: int,
    output_path: Path,
) -> None:
    """Assemble tracks into a mixed set with proper DJ transitions."""
    if len(mp3_files) < 2:
        log.error("Need at least 2 tracks")
        return

    log.info("Mixing %d tracks...", len(mp3_files))
    log.info("Rendering transitions (BPM=%.1f, overlap=%d bars)...", bpm, overlap_bars)

    from app.entities.audio.features import TrackFeatures
    from app.transition.scorer import TransitionScorer

    scorer = TransitionScorer()
    overlap_samples = bars_to_samples(overlap_bars, bpm)

    # Load real features from Supabase for transition scoring
    features_map = _load_features_for_files(mp3_files)
    log.info("Loaded features for %d / %d tracks from Supabase", len(features_map), len(mp3_files))

    # Stream to WAV file — never hold more than 2 tracks in RAM
    wav_path = output_path.with_suffix(".wav")
    total_samples = 0
    prev_features = features_map.get(0, TrackFeatures(bpm=bpm))

    with sf.SoundFile(str(wav_path), mode="w", samplerate=SR, channels=2, format="WAV") as out:
        # Write first track up to the overlap zone
        first_track = load_track(mp3_files[0])
        write_end = max(0, len(first_track) - overlap_samples)
        out.write(first_track[:write_end].astype(np.float32))
        total_samples += write_end

        # Carry over the tail of the current track for the next transition
        carry_tail = first_track[write_end:]
        del first_track

        for i in range(1, len(mp3_files)):
            log.info("  Loading track %d/%d: %s", i + 1, len(mp3_files), mp3_files[i].name)
            next_track = load_track(mp3_files[i])

            # Score transition with real features
            cur_features = features_map.get(i, TrackFeatures(bpm=bpm))
            score = scorer.score(prev_features, cur_features)
            t_type = select_transition(score.overall, overlap_bars)
            prev_features = cur_features

            # Render transition between carry_tail and beginning of next_track
            t_result = render_transition(
                carry_tail,
                next_track,
                bpm,
                t_type,
                overlap_bars,
            )

            log.info(
                "    %2d→%2d: %s (score=%.3f)",
                i,
                i + 1,
                t_result.type_name,
                score.overall,
            )

            # Write the transition blend
            blend = t_result.audio.astype(np.float32)
            # Clip to prevent any overflow
            np.clip(blend, -1.0, 1.0, out=blend)
            out.write(blend)
            total_samples += len(blend)

            # Write the body of next_track (after the overlap zone, minus tail for next transition)
            body_start = t_result.b_start
            if i < len(mp3_files) - 1:
                body_end = max(body_start, len(next_track) - overlap_samples)
                body = next_track[body_start:body_end].astype(np.float32)
                out.write(body)
                total_samples += len(body)
                carry_tail = next_track[body_end:]
            else:
                # Last track — write everything remaining
                body = next_track[body_start:].astype(np.float32)
                out.write(body)
                total_samples += len(body)

            del next_track

    duration_min = total_samples / SR / 60
    log.info("WAV written: %.1f min", duration_min)

    # Convert WAV → MP3
    import subprocess

    log.info("Converting to MP3 (320kbps)...")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "320k",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    wav_path.unlink()

    size_mb = output_path.stat().st_size / 1_048_576
    log.info("Done: %s (%.1f MB, %.1f min)", output_path.name, size_mb, duration_min)


def main() -> None:
    parser = argparse.ArgumentParser(description="DJ mixer with EQ-based transitions")
    parser.add_argument("--input-dir", required=True, help="Directory with numbered MP3s")
    parser.add_argument("--output", default=None, help="Output MP3 path")
    parser.add_argument("--bpm", type=float, default=128.0, help="Set BPM (default 128)")
    parser.add_argument("--overlap-bars", type=int, default=16, help="Overlap duration in bars")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    mp3_files = sorted(input_dir.glob("[0-9][0-9].*.mp3"))
    if not mp3_files:
        mp3_files = sorted(input_dir.glob("[0-9][0-9] *.mp3"))
    if not mp3_files:
        log.error("No numbered MP3 files found in %s", input_dir)
        sys.exit(1)

    log.info("Found %d tracks in %s", len(mp3_files), input_dir)

    output = Path(args.output) if args.output else input_dir / "dj_mix_eq.mp3"

    t0 = time.time()
    assemble_set(mp3_files, args.bpm, args.overlap_bars, output)
    log.info("Total time: %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
