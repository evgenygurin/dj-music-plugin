from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

_DEMUCS_TIMEOUT = 1800

# Cache-versioned model name. Bump when the stem taxonomy changes so that
# previously cached outputs (e.g. 4-stem ``htdemucs``) are not reused.
# Phase 1: model is ``htdemucs_6s`` (5-stem: vocals, drums, bass, other, percussion).
DEFAULT_DEMUCS_MODEL = "htdemucs_6s"


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


# Mapping from Demucs native stem filename → electronic-music stem name.
# Demucs 6s outputs: vocals, drums, bass, other, percussion.
# We rename ``other`` to ``harmonic`` because that is the role in our
# taxonomy (pads / leads / melodic content).
_DEMUCS_STEM_FILE_MAP: dict[str, str] = {
    "vocals": "vocals",
    "drums": "drums",
    "bass": "bass",
    "other": "harmonic",
    "percussion": "percussion",
}


def run_demucs(
    input_path: Path,
    cache_root: Path,
    flac: bool = False,
    model: str = DEFAULT_DEMUCS_MODEL,
) -> dict[str, Path]:
    """Separate audio into stems using Demucs.

    Args:
        input_path: Path to the input audio file.
        cache_root: Root directory for stem cache.
        flac: Whether to output FLAC instead of WAV.
        model: Demucs model. ``htdemucs_6s`` (default) is the electronic-music
            native 5-stem model. Older ``htdemucs`` / ``htdemucs_ft`` 4-stem
            models are supported as a transitional path.
    """
    cache_root.mkdir(parents=True, exist_ok=True)

    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    cache_dir = cache_root / f"{input_path.stem}_{cache_key}"
    stem_dir = cache_dir / model / input_path.stem
    ext = "flac" if flac else "wav"

    # Demucs native stem filenames on disk.
    demucs_native: tuple[str, ...] = (
        (
            "vocals",
            "drums",
            "bass",
            "other",
            "percussion",
        )
        if model.endswith("_6s")
        else ("vocals", "drums", "bass", "other")
    )

    stem_files: dict[str, Path] = {
        _DEMUCS_STEM_FILE_MAP[n]: stem_dir / f"{n}.{ext}" for n in demucs_native
    }

    if all(p.exists() for p in stem_files.values()):
        return stem_files

    wav_stems: dict[str, Path] = {
        _DEMUCS_STEM_FILE_MAP[n]: stem_dir / f"{n}.wav" for n in demucs_native
    }

    need_demucs = not all(p.exists() for p in wav_stems.values())

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

    for name, wav_path in wav_stems.items():
        if not wav_path.exists():
            raise RuntimeError(f"Demucs failed to produce {name} stem at {wav_path}")

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
