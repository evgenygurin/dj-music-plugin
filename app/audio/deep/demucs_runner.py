from __future__ import annotations

import subprocess
from pathlib import Path


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
    device = _detect_device()
    subprocess.run(
        ["python", "-W", "ignore::UserWarning", "-m", "demucs", "-n", "htdemucs", "-d", device, "-o", str(output_dir), str(input_path)],
        check=True, stdout=subprocess.DEVNULL,
    )
    stem_dir = output_dir / "htdemucs" / input_path.stem
    return {
        "vocals": stem_dir / "vocals.wav",
        "drums": stem_dir / "drums.wav",
        "bass": stem_dir / "bass.wav",
        "other": stem_dir / "other.wav",
    }
