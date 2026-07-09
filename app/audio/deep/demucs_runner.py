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


def run_demucs(input_path: Path, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    cache_dir = _CACHE_ROOT / f"{input_path.stem}_{cache_key}"
    stem_dir = cache_dir / "htdemucs" / input_path.stem

    stem_files = {
        "vocals": stem_dir / "vocals.wav",
        "drums": stem_dir / "drums.wav",
        "bass": stem_dir / "bass.wav",
        "other": stem_dir / "other.wav",
    }

    if all(p.exists() for p in stem_files.values()):
        return stem_files

    device = _detect_device()
    subprocess.run(
        ["python", "-W", "ignore::UserWarning", "-m", "demucs", "-n", "htdemucs", "-d", device, "-o", str(cache_dir), str(input_path)],
        check=True, stdout=subprocess.DEVNULL,
    )

    for name, path in stem_files.items():
        if not path.exists():
            raise RuntimeError(f"Demucs failed to produce {name} stem at {path}")

    return stem_files
