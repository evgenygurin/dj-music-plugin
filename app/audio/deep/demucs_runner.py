from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

_DEMUCS_TIMEOUT = 1800

# Demucs ``htdemucs`` (4-stem) is the canonical electronic-music model. We use
# the 4-stem version (vocals/drums/bass/other) because it is the most stable
# pretrained release and the others/guitar/piano heads of ``htdemucs_6s`` bleed
# heavily into drums/other and degrade SDR (per upstream docs).
DEFAULT_DEMUCS_MODEL = "htdemucs"


def _detect_device() -> str:
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


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
    model: str = DEFAULT_DEMUCS_MODEL,
) -> dict[str, Path]:
    """Separate audio into 5 electronic-music stems.

    Returns canonical 5 stems: ``vocals``, ``drums``, ``bass``, ``harmonic``,
    ``percussion``. ``harmonic`` is Demucs ``other`` (pads / leads / melodic
    content). ``percussion`` is derived from the ``drums`` output via a 400 Hz
    split (high-passed content becomes ``percussion``, low-passed keeps the
    rest in ``drums``).

    Args:
        input_path: Path to the input audio file.
        cache_root: Root directory for stem cache.
        flac: Whether to output FLAC instead of WAV.
        model: Demucs model. Default ``htdemucs`` (4-stem, most stable
            electronic-music release).
    """
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

    # Derive ``percussion`` from ``drums`` via 400 Hz split.
    percussion_wav = stem_dir / "percussion.wav"
    drums_wav = stem_dir / "drums.wav"
    if not percussion_wav.exists() and drums_wav.exists():
        tmp_drums = stem_dir / "drums_tmp.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(drums_wav),
                "-filter_complex",
                "[0]lowpass=f=400:poles=2,asetpts=PTS-STARTPTS[drums];[0]highpass=f=400:poles=2,asetpts=PTS-STARTPTS[perc]",
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
