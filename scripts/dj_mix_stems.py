"""Stem-based DJ mixer using demucs for real bass swaps and EQ transitions.

Separates each track into drums/bass/vocals/other via demucs,
then applies transition recipes on individual stems aligned to beatgrid.

Requires: uv sync --extra stems  (demucs + torch)

Usage:
    python scripts/dj_mix_stems.py --input-dir generated-sets/acid-set --bpm 128.2
    python scripts/dj_mix_stems.py --input-dir generated-sets/acid-set --model htdemucs --overlap-bars 16
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stem_mixer")

SR = 44100
STEMS = ("drums", "bass", "vocals", "other")


# ── Stem Separator ───────────────────────────────────────────


@dataclass
class TrackStems:
    """Separated stems for a single track. Each is (samples, channels) float32."""

    drums: np.ndarray
    bass: np.ndarray
    vocals: np.ndarray
    other: np.ndarray
    duration_s: float

    def full_mix(self) -> np.ndarray:
        return self.drums + self.bass + self.vocals + self.other


class StemSeparator:
    """Wraps demucs for stem separation. Tries MLX → MPS → CPU."""

    def __init__(self, model_name: str = "htdemucs", device: str | None = None):
        self._backend = "torch"
        t0 = time.time()

        # Try MLX first (fastest on Apple Silicon, ~3-5x faster than MPS)
        if device is None or device == "mlx":
            try:
                from demucs_mlx import Separator as MLXSeparator

                self._mlx_sep = MLXSeparator(model=model_name, shifts=1)
                self._backend = "mlx"
                log.info("Using demucs-mlx backend (%.1fs)", time.time() - t0)
                return
            except ImportError:
                if device == "mlx":
                    log.error("demucs-mlx not installed: pip install demucs-mlx")
                    sys.exit(1)
                log.info("demucs-mlx not found, falling back to PyTorch")

        # PyTorch fallback
        import torch
        from demucs.pretrained import get_model

        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"  # MPS is ~5-7x faster than CPU on Apple Silicon
            else:
                device = "cpu"

        self._device = device
        log.info("Loading demucs model '%s' on %s...", model_name, device)

        self._model = get_model(model_name)
        self._model.to(torch.device(device))
        self._model.eval()
        self._sources = self._model.sources
        log.info(
            "Model loaded in %.1fs (sources: %s, backend: torch/%s)",
            time.time() - t0,
            self._sources,
            device,
        )

    def separate(self, audio_path: Path) -> TrackStems:
        """Separate a track into 4 stems."""
        if self._backend == "mlx":
            return self._separate_mlx(audio_path)
        return self._separate_torch(audio_path)

    def _separate_mlx(self, audio_path: Path) -> TrackStems:
        """MLX backend — fastest on Apple Silicon."""
        t0 = time.time()
        _origin, stems = self._mlx_sep.separate_audio_file(str(audio_path))

        # demucs-mlx returns numpy arrays as (samples, channels) or (samples,)
        result = {}
        for name in STEMS:
            arr = np.array(stems[name], dtype=np.float32)
            if arr.ndim == 1:
                arr = np.stack([arr, arr], axis=1)
            elif arr.ndim == 2 and arr.shape[0] == 2:
                arr = arr.T  # (channels, samples) → (samples, channels)
            result[name] = arr

        duration_s = result["drums"].shape[0] / SR
        log.info(
            "    Separated in %.1fs (%.1f min track) [mlx]", time.time() - t0, duration_s / 60
        )

        return TrackStems(
            drums=result["drums"],
            bass=result["bass"],
            vocals=result["vocals"],
            other=result["other"],
            duration_s=duration_s,
        )

    def _separate_torch(self, audio_path: Path) -> TrackStems:
        """PyTorch backend (MPS or CPU)."""
        import torch
        from demucs.apply import apply_model
        from demucs.audio import convert_audio

        t0 = time.time()
        data, sr = sf.read(str(audio_path), dtype="float32")
        if data.ndim == 1:
            data = np.stack([data, data], axis=1)
        waveform = torch.from_numpy(data.T)

        waveform = convert_audio(waveform, sr, self._model.samplerate, self._model.audio_channels)
        mix = waveform.unsqueeze(0).to(self._device)

        with torch.no_grad():
            estimates = apply_model(
                self._model,
                mix,
                device=self._device,
                split=True,
                overlap=0.1,  # reduced for speed (0.25 → 0.1)
                shifts=0,  # no random shifts (saves ~50% time)
                progress=False,
            )

        stems = {}
        for i, name in enumerate(self._sources):
            tensor = estimates[0, i].cpu()
            stems[name] = tensor.numpy().T.astype(np.float32)

        duration_s = stems[self._sources[0]].shape[0] / SR
        log.info(
            "    Separated in %.1fs (%.1f min track) [torch/%s]",
            time.time() - t0,
            duration_s / 60,
            self._device,
        )

        return TrackStems(
            drums=stems["drums"],
            bass=stems["bass"],
            vocals=stems["vocals"],
            other=stems["other"],
            duration_s=duration_s,
        )


# ── Beatgrid Helpers ─────────────────────────────────────────


def bars_to_samples(bars: int, bpm: float) -> int:
    return int((60.0 / bpm) * 4 * bars * SR)


def snap_to_phrase(position: int, bpm: float, phrase_bars: int = 4) -> int:
    """Snap sample position to nearest N-bar phrase boundary."""
    phrase = bars_to_samples(phrase_bars, bpm)
    return round(position / phrase) * phrase


# ── Transition Renderers (Stem-Based) ────────────────────────


@dataclass
class StemTransition:
    """Blended overlap region + metadata."""

    audio: np.ndarray  # (samples, channels)
    a_end: int  # cut point in track A
    b_start: int  # start point in track B
    type_name: str


def _fade(n: int, direction: str = "in") -> np.ndarray:
    """Create a fade envelope (n, 1) for broadcasting with stereo."""
    if direction == "in":
        return np.linspace(0, 1, n, dtype=np.float32).reshape(-1, 1)
    return np.linspace(1, 0, n, dtype=np.float32).reshape(-1, 1)


def stem_bass_swap(
    a: TrackStems,
    b: TrackStems,
    overlap_bars: int,
    bpm: float,
    swap_bar: int | None = None,
) -> StemTransition:
    """Real bass swap: mute A's bass, bring in B's bass on a phrase boundary."""
    n = bars_to_samples(overlap_bars, bpm)
    if swap_bar is None:
        swap_bar = overlap_bars // 2
    swap_n = bars_to_samples(swap_bar, bpm)

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
    for arr_name in [
        "a_drums",
        "a_bass",
        "a_vocals",
        "a_other",
        "b_drums",
        "b_bass",
        "b_vocals",
        "b_other",
    ]:
        arr = locals()[arr_name]
        if len(arr) < n:
            pad_width = (
                ((n - len(arr), 0), (0, 0))
                if arr_name.startswith("a")
                else ((0, n - len(arr)), (0, 0))
            )
            locals()[arr_name] = np.pad(arr, pad_width)

    fade_in = _fade(n, "in")
    fade_out = _fade(n, "out")

    # BASS: hard swap at swap point (the key DJ technique)
    bass_mix = np.zeros((n, a_bass.shape[1]), dtype=np.float32)
    # Fade out A's bass leading up to swap point
    bass_fade_out = np.ones((n, 1), dtype=np.float32)
    if swap_n > 0:
        ramp = min(swap_n, bars_to_samples(2, bpm))  # 2-bar ramp
        bass_fade_out[swap_n - ramp : swap_n] = np.linspace(1, 0, ramp).reshape(-1, 1)
    bass_fade_out[swap_n:] = 0
    bass_fade_in = 1 - bass_fade_out
    bass_mix = a_bass * bass_fade_out + b_bass * bass_fade_in

    # DRUMS: gradual crossfade
    drums_mix = a_drums * fade_out + b_drums * fade_in

    # VOCALS: crossfade with slight duck in the middle to avoid clash
    mid_duck = 1.0 - 0.3 * np.exp(-(np.linspace(-2, 2, n) ** 2)).reshape(-1, 1)
    vocals_mix = (a_vocals * fade_out + b_vocals * fade_in) * mid_duck

    # OTHER (synths, pads): smooth crossfade
    other_mix = a_other * fade_out + b_other * fade_in

    blended = (drums_mix + bass_mix + vocals_mix + other_mix).astype(np.float32)

    return StemTransition(
        audio=blended,
        a_end=len(a.drums) - n,
        b_start=n,
        type_name=f"STEM_BASS_SWAP ({overlap_bars} bars, swap@bar {swap_bar})",
    )


def stem_eq_blend(a: TrackStems, b: TrackStems, overlap_bars: int, bpm: float) -> StemTransition:
    """Staggered stem blend: drums first, then other, then bass last."""
    n = bars_to_samples(overlap_bars, bpm)
    n // 3

    def _get(stems: TrackStems, start: bool) -> dict[str, np.ndarray]:
        return {
            name: (getattr(stems, name)[:n] if start else getattr(stems, name)[-n:])
            for name in STEMS
        }

    sa = _get(a, start=False)
    sb = _get(b, start=True)

    # Pad
    for key in STEMS:
        if len(sa[key]) < n:
            sa[key] = np.pad(sa[key], ((n - len(sa[key]), 0), (0, 0)))
        if len(sb[key]) < n:
            sb[key] = np.pad(sb[key], ((0, n - len(sb[key])), (0, 0)))

    # Staggered fades
    drums_fade = np.clip(np.linspace(-0.3, 1.3, n), 0, 1).reshape(-1, 1)  # earliest
    other_fade = np.clip(np.linspace(-0.1, 1.1, n), 0, 1).reshape(-1, 1)
    vocals_fade = np.linspace(0, 1, n).reshape(-1, 1)
    bass_fade = np.clip(np.linspace(0.1, 0.9, n), 0, 1).reshape(-1, 1)  # latest

    blended = (
        sa["drums"] * (1 - drums_fade)
        + sb["drums"] * drums_fade
        + sa["bass"] * (1 - bass_fade)
        + sb["bass"] * bass_fade
        + sa["vocals"] * (1 - vocals_fade)
        + sb["vocals"] * vocals_fade
        + sa["other"] * (1 - other_fade)
        + sb["other"] * other_fade
    ).astype(np.float32)

    return StemTransition(
        audio=blended,
        a_end=len(a.drums) - n,
        b_start=n,
        type_name=f"STEM_EQ_BLEND ({overlap_bars} bars)",
    )


def stem_filter_sweep(
    a: TrackStems, b: TrackStems, overlap_bars: int, bpm: float
) -> StemTransition:
    """Kill A's bass and vocals, sweep out other/drums, bring in B clean."""
    n = bars_to_samples(overlap_bars, bpm)

    def _tail(stems: TrackStems) -> dict[str, np.ndarray]:
        return {name: getattr(stems, name)[-n:] for name in STEMS}

    def _head(stems: TrackStems) -> dict[str, np.ndarray]:
        return {name: getattr(stems, name)[:n] for name in STEMS}

    sa, sb = _tail(a), _head(b)
    for key in STEMS:
        if len(sa[key]) < n:
            sa[key] = np.pad(sa[key], ((n - len(sa[key]), 0), (0, 0)))
        if len(sb[key]) < n:
            sb[key] = np.pad(sb[key], ((0, n - len(sb[key])), (0, 0)))

    fade_in = _fade(n, "in")
    fade_out = _fade(n, "out")

    # Kill A's bass and vocals quickly (first quarter)
    quick_kill = np.ones((n, 1), dtype=np.float32)
    quarter = n // 4
    quick_kill[:quarter] = np.linspace(1, 0, quarter).reshape(-1, 1)
    quick_kill[quarter:] = 0

    blended = (
        sa["drums"] * fade_out
        + sb["drums"] * fade_in  # drums crossfade
        + sa["bass"] * quick_kill
        + sb["bass"] * (1 - quick_kill)  # bass: quick swap
        + sa["vocals"] * quick_kill  # vocals: kill A's
        + sb["vocals"] * fade_in  # vocals: bring in B's
        + sa["other"] * fade_out
        + sb["other"] * fade_in  # other: crossfade
    ).astype(np.float32)

    return StemTransition(
        audio=blended,
        a_end=len(a.drums) - n,
        b_start=n,
        type_name=f"STEM_FILTER_SWEEP ({overlap_bars} bars)",
    )


def stem_echo_out(a: TrackStems, b: TrackStems, overlap_bars: int, bpm: float) -> StemTransition:
    """Echo out A's melodic stems, keep drums crossfading, hard-swap bass."""
    n = bars_to_samples(overlap_bars, bpm)

    sa = {name: getattr(a, name)[-n:] for name in STEMS}
    sb = {name: getattr(b, name)[:n] for name in STEMS}
    for key in STEMS:
        if len(sa[key]) < n:
            sa[key] = np.pad(sa[key], ((n - len(sa[key]), 0), (0, 0)))
        if len(sb[key]) < n:
            sb[key] = np.pad(sb[key], ((0, n - len(sb[key])), (0, 0)))

    fade_in = _fade(n, "in")
    # Exponential fade for echo effect on vocals/other
    exp_fade = np.exp(-np.linspace(0, 5, n, dtype=np.float32)).reshape(-1, 1)

    # Add simple delay echo to A's vocals and other
    delay = bars_to_samples(1, bpm) // 2  # half-bar echo
    a_voc_echo = np.zeros_like(sa["vocals"])
    if delay < n:
        a_voc_echo[delay:] = sa["vocals"][:-delay] * 0.4

    # Bass: swap at halfway
    half = n // 2
    bass_mix = np.concatenate([sa["bass"][:half], sb["bass"][half:]])

    blended = (
        sa["drums"] * (1 - fade_in)
        + sb["drums"] * fade_in  # drums: crossfade
        + bass_mix  # bass: hard swap
        + (sa["vocals"] + a_voc_echo) * exp_fade
        + sb["vocals"] * fade_in  # vocals: echo out + bring in
        + sa["other"] * exp_fade
        + sb["other"] * fade_in  # other: fade with echo feel
    ).astype(np.float32)

    return StemTransition(
        audio=blended,
        a_end=len(a.drums) - n,
        b_start=n,
        type_name=f"STEM_ECHO_OUT ({overlap_bars} bars)",
    )


# ── Transition Selection & Dispatch ──────────────────────────


def select_and_render(
    a: TrackStems,
    b: TrackStems,
    score_overall: float,
    overlap_bars: int,
    bpm: float,
) -> StemTransition:
    """Choose transition type based on score and render with stems."""
    if score_overall >= 0.85:
        return stem_bass_swap(a, b, overlap_bars, bpm)
    elif score_overall >= 0.70:
        return stem_eq_blend(a, b, overlap_bars, bpm)
    elif score_overall >= 0.55:
        return stem_filter_sweep(a, b, overlap_bars, bpm)
    else:
        return stem_echo_out(a, b, overlap_bars, bpm)


# ── Main ─────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Stem-based DJ mixer (demucs)")
    parser.add_argument("--input-dir", required=True, help="Directory with numbered MP3s")
    parser.add_argument("--output", default=None, help="Output MP3 path")
    parser.add_argument("--bpm", type=float, default=128.0, help="Set BPM")
    parser.add_argument("--overlap-bars", type=int, default=16, help="Overlap in bars")
    parser.add_argument("--model", default="htdemucs", help="Demucs model (htdemucs, htdemucs_ft)")
    parser.add_argument("--device", default=None, help="torch device (cuda, mps, cpu)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    mp3_files = sorted(input_dir.glob("[0-9][0-9].*.mp3")) or sorted(
        input_dir.glob("[0-9][0-9] *.mp3")
    )
    if not mp3_files:
        log.error("No numbered MP3 files in %s", input_dir)
        sys.exit(1)

    log.info("Found %d tracks", len(mp3_files))
    output = Path(args.output) if args.output else input_dir / "dj_mix_stems.mp3"

    t_total = time.time()

    # Initialize stem separator
    separator = StemSeparator(model_name=args.model, device=args.device)

    # Separate all tracks
    log.info("=" * 60)
    log.info("PHASE 1: Separating stems for %d tracks", len(mp3_files))
    log.info("=" * 60)
    all_stems: list[TrackStems] = []
    for i, f in enumerate(mp3_files):
        log.info("  [%d/%d] %s", i + 1, len(mp3_files), f.name)
        all_stems.append(separator.separate(f))

    # Render transitions and write output
    log.info("=" * 60)
    log.info("PHASE 2: Rendering stem-based transitions")
    log.info("=" * 60)

    from app.entities.audio.features import TrackFeatures
    from app.transition.scorer import TransitionScorer

    scorer = TransitionScorer()
    overlap_samples = bars_to_samples(args.overlap_bars, args.bpm)
    wav_path = output.with_suffix(".wav")
    total_samples = 0

    with sf.SoundFile(str(wav_path), mode="w", samplerate=SR, channels=2, format="WAV") as out:
        # Write first track body (minus overlap tail)
        first_mix = all_stems[0].full_mix()
        write_end = max(0, len(first_mix) - overlap_samples)
        out.write(np.clip(first_mix[:write_end], -1, 1).astype(np.float32))
        total_samples += write_end

        for i in range(1, len(all_stems)):
            a_stems = all_stems[i - 1]
            b_stems = all_stems[i]

            # Score transition
            score = scorer.score(TrackFeatures(bpm=args.bpm), TrackFeatures(bpm=args.bpm))

            # Render stem-based transition
            tr = select_and_render(a_stems, b_stems, score.overall, args.overlap_bars, args.bpm)

            log.info("  %2d→%2d: %s (score=%.3f)", i, i + 1, tr.type_name, score.overall)

            # Write transition blend
            out.write(np.clip(tr.audio, -1, 1).astype(np.float32))
            total_samples += len(tr.audio)

            # Write body of track B (after overlap, minus tail for next)
            b_mix = b_stems.full_mix()
            if i < len(all_stems) - 1:
                body = b_mix[tr.b_start : max(tr.b_start, len(b_mix) - overlap_samples)]
            else:
                body = b_mix[tr.b_start :]
            out.write(np.clip(body, -1, 1).astype(np.float32))
            total_samples += len(body)

    duration_min = total_samples / SR / 60
    log.info("WAV: %.1f min", duration_min)

    # Convert to MP3
    log.info("Converting to MP3 (320kbps)...")
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
            str(output),
        ],
        capture_output=True,
        check=True,
    )
    wav_path.unlink()

    size_mb = output.stat().st_size / 1_048_576
    log.info("=" * 60)
    log.info("DONE in %.1fs", time.time() - t_total)
    log.info("Output: %s (%.1f MB, %.1f min)", output, size_mb, duration_min)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
