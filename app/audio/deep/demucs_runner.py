from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

_DEMUCS_TIMEOUT = 1800


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
) -> dict[str, Path]:
    cache_root.mkdir(parents=True, exist_ok=True)

    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    cache_dir = cache_root / f"{input_path.stem}_{cache_key}"
    stem_dir = cache_dir / "htdemucs_6s" / input_path.stem
    ext = "flac" if flac else "wav"

    stem_files: dict[str, Path] = {
        "vocals": stem_dir / f"vocals.{ext}",
        "drums": stem_dir / f"drums.{ext}",
        "bass": stem_dir / f"bass.{ext}",
        "other": stem_dir / f"other.{ext}",
        "percussion": stem_dir / f"percussion.{ext}",
    }

    if all(p.exists() for p in stem_files.values()):
        return stem_files

    wav_stems: dict[str, Path] = {
        "vocals": stem_dir / "vocals.wav",
        "drums": stem_dir / "drums.wav",
        "bass": stem_dir / "bass.wav",
        "other": stem_dir / "other.wav",
    }

    # Migration path: 4 demucs stems exist but no percussion
    # Run demucs_6s to get the 5th stem
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
                "htdemucs_6s",
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

    perc_wav = stem_dir / "percussion.wav"
    if not perc_wav.exists():
        drums_wav = wav_stems["drums"]
        tmp_drums = stem_dir / "drums_tmp.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(drums_wav),
                "-filter_complex",
                "[0]lowpass=f=400:poles=2,asetpts=PTS-STARTPTS[drums];"
                "[0]highpass=f=400:poles=2,asetpts=PTS-STARTPTS[perc]",
                "-map",
                "[drums]",
                str(tmp_drums),
                "-map",
                "[perc]",
                str(perc_wav),
            ],
            check=True,
            timeout=300,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        tmp_drums.replace(drums_wav)
    wav_stems["percussion"] = perc_wav

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
