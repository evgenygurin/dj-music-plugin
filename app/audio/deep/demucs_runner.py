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
# Public ``htdemucs_6s`` outputs 6 stems: vocals, drums, bass, other, guitar, piano.
# Our electronic taxonomy is 5 stems: vocals, drums, bass, harmonic, percussion.
# We map ``other``/``guitar``/``piano`` → ``harmonic`` (pads/leads) and derive
# ``percussion`` from drums when the model does not provide it (fallback split).
_DEMUCS_STEM_FILE_MAP: dict[str, str] = {
    "vocals": "vocals",
    "drums": "drums",
    "bass": "bass",
    "other": "harmonic",
    "guitar": "harmonic",
    "piano": "harmonic",
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
    # Public htdemucs_6s is 6 stems (vocals/drums/bass/other/guitar/piano);
    # custom 6s is 5 stems (vocals/drums/bass/other/percussion); 4s is 4.
    # We handle all by producing the canonical 5 (vocals/drums/bass/harmonic/percussion).
    expected_stems: tuple[str, ...] = ("vocals", "drums", "bass", "harmonic", "percussion")
    stem_files: dict[str, Path] = {name: stem_dir / f"{name}.{ext}" for name in expected_stems}
    if all(p.exists() for p in stem_files.values()):
        return stem_files
    wav_expected: dict[str, Path] = {name: stem_dir / f"{name}.wav" for name in expected_stems}
    if all(p.exists() for p in wav_expected.values()) and ext == "wav":
        return wav_expected
    # Need flac conversion, fall through if ext == "flac"

    # Check native files to decide if Demucs is needed
    demucs_native_6s_public: tuple[str, ...] = (
        "vocals",
        "drums",
        "bass",
        "other",
        "guitar",
        "piano",
    )
    demucs_native_6s_custom: tuple[str, ...] = ("vocals", "drums", "bass", "other", "percussion")
    demucs_native_4: tuple[str, ...] = ("vocals", "drums", "bass", "other")
    candidates = (
        [demucs_native_6s_public, demucs_native_6s_custom, demucs_native_4]
        if model.endswith("_6s")
        else [demucs_native_4]
    )
    need_demucs = True
    for cand in candidates:
        if all((stem_dir / f"{n}.wav").exists() for n in cand):
            need_demucs = False
            break
    # Also check if expected already exists (harmonic/percussion derived)
    if all(p.exists() for p in wav_expected.values()):
        need_demucs = False

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

    # Post-process: public 6s gives other+guitar+piano -> harmonic; derive percussion if missing
    other_wav = stem_dir / "other.wav"
    guitar_wav = stem_dir / "guitar.wav"
    piano_wav = stem_dir / "piano.wav"
    harmonic_wav = stem_dir / "harmonic.wav"
    if not harmonic_wav.exists() and other_wav.exists():
        # Mix other + guitar + piano into harmonic when available
        harmonic_sources = [other_wav]
        if guitar_wav.exists():
            harmonic_sources.append(guitar_wav)
        if piano_wav.exists():
            harmonic_sources.append(piano_wav)
        if len(harmonic_sources) > 1:
            amix_inputs = []
            filter_parts = []
            for idx, _ in enumerate(harmonic_sources):
                filter_parts.append(
                    f"[{idx}:a]aformat=sample_fmts=fltp:channel_layouts=stereo,aresample=async=1[a{idx}]"
                )
                amix_inputs.append(f"[a{idx}]")
            amix_filter = f"{';'.join(filter_parts)};{''.join(amix_inputs)}amix=inputs={len(harmonic_sources)}:duration=longest:dropout_transition=0,aresample=async=1[harmonic]"
            cmd = ["ffmpeg", "-y"]
            for inp in harmonic_sources:
                cmd.extend(["-i", str(inp)])
            cmd.extend(["-filter_complex", amix_filter, "-map", "[harmonic]", str(harmonic_wav)])
            subprocess.run(
                cmd, check=True, timeout=300, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif other_wav.exists():
            # No guitar/piano, just copy other -> harmonic
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(other_wav), "-c:a", "pcm_s16le", str(harmonic_wav)],
                check=True,
                timeout=300,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    # Derive percussion from drums if missing (400 Hz split, legacy fallback)
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
