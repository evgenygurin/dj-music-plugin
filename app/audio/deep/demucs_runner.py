from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

_DEMUCS_TIMEOUT = 1800

# Demucs ``htdemucs`` (4-stem) is the canonical electronic-music model. We use
# the 4-stem version (vocals/drums/bass/other) because it is the most stable
# pretrained release and the others/guitar/piano heads of ``htdemucs_6s`` bleed
# heavily into drums/other and degrade SDR (per upstream docs).
#
# Set ``DJ_DEMUCS_MODEL=htdemucs_ft`` to opt into the fine-tuned bag (4 sub-models,
# +0.66 dB vocals / +0.60 dB bass SDR on MUSDB18-HQ) at ~2.4x wall-clock cost.
# See ``AGENTS.md §8`` for the full SDR table.
DEFAULT_DEMUCS_MODEL = "htdemucs"

# Quality knobs. CLI defaults for ``demucs -n htdemucs`` are shifts=0 / overlap=0.25
# / segment=Default / clip-mode=rescale / jobs=0 — these give the lowest quality
# of any sane configuration. We raise shifts to 5 (the equivariant-stabilization
# trick from Défossez et al. 2021, paper used 10), keep overlap at 0.25 (best
# quality/speed tradeoff — see upstream docs), and force segment=7.8 to avoid
# model-default chunking edge artifacts on long techno tracks. 7.8 is the
# HTDemucs Transformer hard limit (≤7.8s); 10 triggers silent truncation.
DEMUCS_SHIFTS = 5
DEMUCS_OVERLAP = 0.25
DEMUCS_SEGMENT = 7.8
DEMUCS_CLIP_MODE = "rescale"
try:
    import psutil as _psutil  # type: ignore

    _available_mem = _psutil.virtual_memory().available
    DEMUCS_JOBS = 0 if _available_mem < 4_000_000_000 else 2
    # 8GB M2: available <3GB under load → disable MPS high-watermark caching
    # to avoid OOM (PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0). Brief sets it
    # unconditionally; global constraint gates on <3GB — unify: set when
    # psutil reports <3GB, otherwise still setdefault (no-op if already set).
    if _available_mem < 3_000_000_000:
        os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
    else:
        os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
except ImportError:
    DEMUCS_JOBS = 0
    os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")

# Percussion split cutoff. We pull hi-hats / cymbals / shakers OUT of ``drums``
# and into ``percussion`` via a high-pass filter. 2000 Hz keeps the kick body
# and low toms in ``drums`` (where DJ listeners expect them) while routing the
# metallic cymbal energy to ``percussion`` (where the subgenre presets can EQ
# it independently for hi-hat control). The old 400 Hz split was a stop-gap
# that destroyed kick punch.
PERCUSSION_SPLIT_HZ = 2000


def _detect_device() -> str:
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _demucs_model() -> str:
    """Resolve the active Demucs model (env override → default)."""
    return os.environ.get("DJ_DEMUCS_MODEL", DEFAULT_DEMUCS_MODEL)


def _run_with_retry(args: list[str], timeout: int = _DEMUCS_TIMEOUT) -> None:
    for attempt in range(2):
        try:
            subprocess.run(
                args,
                check=True,
                timeout=timeout,
                stdout=subprocess.DEVNULL,
            )
            return
        except subprocess.TimeoutExpired:
            if attempt == 1:
                raise
            import gc

            gc.collect()
            try:
                import torch

                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
            except Exception:
                pass


def run_demucs(
    input_path: Path,
    cache_root: Path,
    flac: bool = False,
    model: str | None = None,
) -> dict[str, Path]:
    """Separate audio into 5 electronic-music stems.

    Returns canonical 5 stems: ``vocals``, ``drums``, ``bass``, ``harmonic``,
    ``percussion``. ``harmonic`` is Demucs ``other`` (pads / leads / melodic
    content). ``percussion`` is derived from the ``drums`` output via a 2 kHz
    high-pass split (cymbals/hi-hats — kick body stays in ``drums``).

    Args:
        input_path: Path to the input audio file.
        cache_root: Root directory for stem cache.
        flac: Whether to output FLAC instead of WAV.
        model: Demucs model. Default ``htdemucs`` (4-stem, single-file, fast).
            Pass ``htdemucs_ft`` for the fine-tuned 4-bag (slower, better SDR).
    """
    model = model or _demucs_model()
    cache_root.mkdir(parents=True, exist_ok=True)

    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    cache_dir = cache_root / f"{input_path.stem}_{cache_key}"
    stem_dir = cache_dir / model / input_path.stem
    ext = "flac" if flac else "wav"

    expected_stems: tuple[str, ...] = ("vocals", "drums", "bass", "harmonic", "percussion")
    stem_files: dict[str, Path] = {name: stem_dir / f"{name}.{ext}" for name in expected_stems}
    if all(p.exists() for p in stem_files.values()):
        return stem_files
    wav_expected: dict[str, Path] = {name: stem_dir / f"{name}.wav" for name in expected_stems}
    if all(p.exists() for p in wav_expected.values()) and ext == "wav":
        return wav_expected
    # Need flac conversion, fall through if ext == "flac"

    # Cache hit on the raw Demucs 4-stem output (vocals/drums/bass/other).
    demucs_native_4: tuple[str, ...] = ("vocals", "drums", "bass", "other")
    raw_demucs_present = all((stem_dir / f"{n}.wav").exists() for n in demucs_native_4)
    canonical_present = all(p.exists() for p in wav_expected.values())
    need_demucs = not raw_demucs_present and not canonical_present

    if need_demucs:
        device = _detect_device()
        _run_with_retry(
            [
                "python",
                "-W",
                "ignore::UserWarning",
                "-m",
                "demucs",
                "-n",
                model,
                "-d",
                device,
                "-o",
                str(cache_dir),
                "--shifts",
                str(DEMUCS_SHIFTS),
                "--overlap",
                str(DEMUCS_OVERLAP),
                "--segment",
                str(DEMUCS_SEGMENT),
                "--clip-mode",
                DEMUCS_CLIP_MODE,
                "-j",
                str(DEMUCS_JOBS),
                str(input_path),
            ]
        )

    # Build ``harmonic`` from Demucs ``other``.
    other_wav = stem_dir / "other.wav"
    harmonic_wav = stem_dir / "harmonic.wav"
    if not harmonic_wav.exists() and other_wav.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(other_wav), "-c:a", "pcm_s16le", str(harmonic_wav)],
            check=True,
            timeout=300,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Derive ``percussion`` from ``drums`` via high-pass split (cymbals/hi-hats).
    # 2 kHz keeps the kick fundamental (typically 40-120 Hz) and the snare body
    # (150-400 Hz) inside ``drums`` where they belong — only the metallic
    # energy above 2 kHz (hi-hats, ride cymbals, shakers) leaks into
    # ``percussion`` for separate EQ control by subgenre presets.
    percussion_wav = stem_dir / "percussion.wav"
    drums_wav = stem_dir / "drums.wav"
    if not percussion_wav.exists() and drums_wav.exists():
        tmp_drums = stem_dir / "drums_tmp.wav"
        cutoff = PERCUSSION_SPLIT_HZ
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(drums_wav),
                "-filter_complex",
                (
                    f"[0]lowpass=f={cutoff}:poles=2,asetpts=PTS-STARTPTS[drums];"
                    f"[0]highpass=f={cutoff}:poles=2,asetpts=PTS-STARTPTS[perc]"
                ),
                "-map",
                "[drums]",
                str(tmp_drums),
                "-map",
                "[perc]",
                str(percussion_wav),
            ],
            check=True,
            timeout=300,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        tmp_drums.replace(drums_wav)

    wav_stems: dict[str, Path] = {name: stem_dir / f"{name}.wav" for name in expected_stems}
    for name, wav_path in wav_stems.items():
        if not wav_path.exists():
            raise RuntimeError(
                f"Demucs failed to produce {name} stem at {wav_path} (checked {stem_dir})"
            )

    if flac:
        for name, wav_path in wav_stems.items():
            flac_path = stem_files[name]
            if not flac_path.exists():
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(wav_path),
                        "-c:a",
                        "flac",
                        "-compression_level",
                        "8",
                        str(flac_path),
                    ],
                    check=True,
                    timeout=300,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            wav_path.unlink(missing_ok=True)

    return stem_files
