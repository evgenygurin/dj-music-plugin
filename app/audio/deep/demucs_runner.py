from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

_CACHE_ROOT = Path("/tmp/dj_stems")


def _detect_device() -> str:
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def run_demucs(
    input_path: Path,
    output_dir: Path,
    cache_root: Path | None = None,
    flac: bool = False,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    root = cache_root if cache_root is not None else _CACHE_ROOT
    cache_dir = root / f"{input_path.stem}_{cache_key}"
    stem_dir = cache_dir / "htdemucs" / input_path.stem
    ext = "flac" if flac else "wav"

    stem_files = {
        "vocals": stem_dir / f"vocals.{ext}",
        "drums": stem_dir / f"drums.{ext}",
        "bass": stem_dir / f"bass.{ext}",
        "other": stem_dir / f"other.{ext}",
    }

    if all(p.exists() for p in stem_files.values()):
        return stem_files

    device = _detect_device()
    subprocess.run(
        [
            "python",
            "-W",
            "ignore::UserWarning",
            "-m",
            "demucs",
            "-n",
            "htdemucs",
            "-d",
            device,
            "-o",
            str(cache_dir),
            str(input_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    wav_stems = {
        "vocals": stem_dir / "vocals.wav",
        "drums": stem_dir / "drums.wav",
        "bass": stem_dir / "bass.wav",
        "other": stem_dir / "other.wav",
    }

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
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            wav_path.unlink(missing_ok=True)

    return stem_files
