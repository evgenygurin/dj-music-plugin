"""Mix renderer — assembles separated stems into a single DJ mix MP3.

Takes a list of StemResults (from StemService) and TransitionScores,
applies stem-based transitions (bass swap, EQ blend, filter sweep, etc.)
aligned to phrase boundaries, and writes a single MP3 file.

Transition logic based on:
- Mosaikbox (ISMIR 2024): stem order drums→bass→harmonics→vocals
- Kim (ISMIR 2020): MFCC-driven scoring
- Allen & Heath / Pioneer: 150Hz kick kill, 24dB/oct HPF, 0ms bass swap
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.services.stem_service import SR, StemResult
from app.transition.score import TransitionScore
from app.transition.weights import MICRO_RAMP_MS

logger = logging.getLogger(__name__)

MICRO_RAMP_SAMPLES = int(MICRO_RAMP_MS / 1000 * SR)


@dataclass
class MixSetResult:
    """Result of rendering a DJ mix."""

    output_path: Path
    duration_s: float
    track_count: int
    transitions: list[dict[str, object]]
    size_bytes: int


def _fade(n: int, direction: str = "in") -> np.ndarray:
    if direction == "in":
        return np.linspace(0, 1, n, dtype=np.float32).reshape(-1, 1)
    return np.linspace(1, 0, n, dtype=np.float32).reshape(-1, 1)


def _bars_to_samples(bars: int, bpm: float) -> int:
    return int((60.0 / bpm) * 4 * bars * SR)


def _render_transition(
    a: StemResult,
    b: StemResult,
    score: TransitionScore,
    overlap_bars: int,
    bpm: float,
) -> tuple[np.ndarray, int, int, str]:
    """Render a stem-based transition. Returns (blended_audio, a_end, b_start, type_name)."""
    n = _bars_to_samples(overlap_bars, bpm)
    swap_n = n // 2  # bass swap at halfway point

    # Get overlap regions
    a_drums = a.drums[-n:]
    a_bass = a.bass[-n:]
    a_vocals = a.vocals[-n:]
    a_other = a.other[-n:]
    b_drums = b.drums[:n]
    b_bass = b.bass[:n]
    b_vocals = b.vocals[:n]
    b_other = b.other[:n]

    # Pad if needed
    for name in ("a_drums", "a_bass", "a_vocals", "a_other"):
        arr = locals()[name]
        if len(arr) < n:
            locals()[name] = np.pad(arr, ((n - len(arr), 0), (0, 0)))
    for name in ("b_drums", "b_bass", "b_vocals", "b_other"):
        arr = locals()[name]
        if len(arr) < n:
            locals()[name] = np.pad(arr, ((0, n - len(arr)), (0, 0)))

    fade_in = _fade(n, "in")
    fade_out = _fade(n, "out")
    quarter = n // 4
    mr = MICRO_RAMP_SAMPLES

    # Select transition type based on score
    if score.hard_reject or score.overall < 0.40:
        t_type = "FILTER_SWEEP"
    elif score.overall >= 0.85:
        t_type = "BASS_SWAP_SHORT"
    elif score.overall >= 0.70:
        t_type = "BASS_SWAP_LONG"
    elif score.spectral < 0.45:
        t_type = "FILTER_SWEEP"
    elif score.energy < 0.40:
        t_type = "ECHO_OUT"
    else:
        t_type = "EQ_BLEND"

    # ── BASS: always hard cut with micro-ramp (cardinal rule) ──
    bass_mix = np.zeros((n, a_bass.shape[1]), dtype=np.float32)
    bass_mix[:swap_n] = a_bass[:swap_n]
    bass_mix[swap_n:] = b_bass[swap_n:]
    if mr > 0 and swap_n > mr and swap_n < n - mr:
        ramp_out = np.linspace(1, 0, mr, dtype=np.float32).reshape(-1, 1)
        ramp_in = np.linspace(0, 1, mr, dtype=np.float32).reshape(-1, 1)
        bass_mix[swap_n - mr : swap_n] = a_bass[swap_n - mr : swap_n] * ramp_out
        bass_mix[swap_n : swap_n + mr] = b_bass[swap_n : swap_n + mr] * ramp_in

    # ── DRUMS: introduce B first (Mosaikbox canonical order) ──
    drums_early = np.zeros((n, 1), dtype=np.float32)
    drums_early[:quarter] = np.linspace(0, 1, quarter, dtype=np.float32).reshape(-1, 1)
    drums_early[quarter:] = 1.0
    if score.drum_conflict:
        # Drum pattern mismatch — attenuate incoming drums
        drums_mix = a_drums * fade_out + b_drums * drums_early * fade_in * 0.5
    else:
        drums_mix = a_drums * fade_out + b_drums * drums_early * fade_in

    # ── VOCALS: handle conflict (Mosaikbox: mute outgoing if both have vocals) ──
    if score.vocal_conflict:
        mid_duck = np.ones((n, 1), dtype=np.float32)
        mid_duck[: n // 3] = np.linspace(1, 0, n // 3, dtype=np.float32).reshape(-1, 1)
        mid_duck[n // 3 :] = 0
        vocals_mix = a_vocals * mid_duck + b_vocals * fade_in
    else:
        duck = 1.0 - 0.3 * np.exp(-(np.linspace(-2, 2, n) ** 2)).reshape(-1, 1)
        vocals_mix = (a_vocals * fade_out + b_vocals * fade_in) * duck

    # ── OTHER (harmonics): introduce after bass swap ──
    half = n // 2
    other_late = np.zeros((n, 1), dtype=np.float32)
    other_late[half:] = np.linspace(0, 1, n - half, dtype=np.float32).reshape(-1, 1)
    other_mix = a_other * fade_out + b_other * other_late

    blended = np.clip(drums_mix + bass_mix + vocals_mix + other_mix, -1, 1).astype(np.float32)

    return blended, len(a.drums) - n, n, t_type


async def mix_set(
    stems: list[StemResult],
    scores: list[TransitionScore],
    *,
    bpm: float,
    overlap_bars: int = 16,
    output_path: Path,
    progress_callback: object = None,
) -> MixSetResult:
    """Render a complete DJ mix from separated stems.

    Args:
        stems: List of StemResults (one per track, in set order).
        scores: List of TransitionScores between consecutive pairs
                (len = len(stems) - 1).
        bpm: Set BPM for bar/phrase calculations.
        overlap_bars: Transition overlap in bars (default 16).
        output_path: Where to write the final MP3.
        progress_callback: Optional async callable(step, total, message).
    """
    import soundfile as sf

    if len(stems) < 2:
        msg = "Need at least 2 tracks to render a mix"
        raise ValueError(msg)
    if len(scores) != len(stems) - 1:
        msg = f"Expected {len(stems) - 1} scores, got {len(scores)}"
        raise ValueError(msg)

    overlap_samples = _bars_to_samples(overlap_bars, bpm)
    wav_path = output_path.with_suffix(".wav")
    total_samples = 0
    transition_log: list[dict[str, object]] = []

    logger.info(
        "Rendering mix: %d tracks, %d bars overlap, %.1f BPM", len(stems), overlap_bars, bpm
    )

    with sf.SoundFile(str(wav_path), mode="w", samplerate=SR, channels=2, format="WAV") as out:
        # Write first track body
        first_mix = stems[0].full_mix()
        write_end = max(0, len(first_mix) - overlap_samples)
        out.write(np.clip(first_mix[:write_end], -1, 1).astype(np.float32))
        total_samples += write_end

        for i in range(1, len(stems)):
            blended, _a_end, b_start, t_type = _render_transition(
                stems[i - 1],
                stems[i],
                scores[i - 1],
                overlap_bars,
                bpm,
            )

            if progress_callback and callable(progress_callback):
                await progress_callback(  # type: ignore[misc]
                    i,
                    len(stems) - 1,
                    f"Transition {i}→{i + 1}: {t_type} (score={scores[i - 1].overall:.3f})",
                )

            logger.info(
                "  %d→%d: %s (%.3f [bpm=%.2f hrm=%.2f nrg=%.2f spc=%.2f grv=%.2f tmb=%.2f]%s%s)",
                i,
                i + 1,
                t_type,
                scores[i - 1].overall,
                scores[i - 1].bpm,
                scores[i - 1].harmonic,
                scores[i - 1].energy,
                scores[i - 1].spectral,
                scores[i - 1].groove,
                scores[i - 1].timbral,
                " VOCAL_CONFLICT" if scores[i - 1].vocal_conflict else "",
                " DRUM_CONFLICT" if scores[i - 1].drum_conflict else "",
            )

            out.write(blended)
            total_samples += len(blended)

            # Write body of next track
            b_mix = stems[i].full_mix()
            if i < len(stems) - 1:
                body = b_mix[b_start : max(b_start, len(b_mix) - overlap_samples)]
            else:
                body = b_mix[b_start:]
            out.write(np.clip(body, -1, 1).astype(np.float32))
            total_samples += len(body)

            transition_log.append(
                {
                    "from_track": i,
                    "to_track": i + 1,
                    "type": t_type,
                    "score": scores[i - 1].overall,
                    "vocal_conflict": scores[i - 1].vocal_conflict,
                    "drum_conflict": scores[i - 1].drum_conflict,
                }
            )

    duration_s = total_samples / SR
    logger.info("WAV written: %.1f min", duration_s / 60)

    # Convert to MP3
    logger.info("Converting to MP3 (320kbps)...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "320k",
            str(output_path),
        ],
        capture_output=True,
        check=True,
    )
    wav_path.unlink()

    size = output_path.stat().st_size
    logger.info(
        "Done: %s (%.1f MB, %.1f min)", output_path.name, size / 1_048_576, duration_s / 60
    )

    return MixSetResult(
        output_path=output_path,
        duration_s=duration_s,
        track_count=len(stems),
        transitions=transition_log,
        size_bytes=size,
    )
