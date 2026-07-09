from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def analyze_structure(
    audio_path: Path,
    stem_paths: dict[str, Path],
) -> list[dict[str, object]]:
    audio, sr = sf.read(str(audio_path))
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    try:
        import essentia.standard as es
    except ImportError:
        return []

    w = es.Windowing(type="hann")
    spectrum = es.Spectrum()
    mfcc_algo = es.MFCC(sampleRate=sr)
    hp_generator = es.FrameGenerator(audio, frameSize=4096, hopSize=1024)

    mfcc_frames = []
    for frame in hp_generator:
        spec = spectrum(w(frame))
        _mfcc_bands, mfcc_coeffs = mfcc_algo(spec)
        mfcc_frames.append(mfcc_coeffs)

    if len(mfcc_frames) < 4:
        return []

    mfcc_stack = np.array(mfcc_frames, dtype=np.float32)
    sbic = es.SBic()
    boundaries = sbic(mfcc_stack)
    if len(boundaries) == 0:
        return []

    hop_size = 1024
    sections = []
    for i, boundary in enumerate(boundaries):
        start_frame = int(boundaries[i - 1]) if i > 0 else 0
        end_frame = int(boundary)
        start_ms = int(start_frame * hop_size / sr * 1000)
        end_ms = int(end_frame * hop_size / sr * 1000)

        section_audio = audio[start_frame * hop_size : end_frame * hop_size + 4096]
        if len(section_audio) < 512:
            continue

        energy = float(np.sqrt(np.mean(section_audio**2)))
        rms_db = float(20 * np.log10(max(energy, 1e-10)))

        spec_centroid = float(np.mean(librosa_feature_spectral_centroid(
            y=section_audio, sr=sr, n_fft=2048, hop_length=512
        )))

        stem_energy: dict[str, float] = {}
        for stem_name, stem_path in stem_paths.items():
            stem_audio, _ = sf.read(str(stem_path))
            if stem_audio.ndim == 2:
                stem_audio = np.mean(stem_audio, axis=1)
            seg = stem_audio[start_frame * hop_size : end_frame * hop_size + 4096]
            if len(seg) > 0:
                stem_energy[stem_name] = round(float(np.sqrt(np.mean(seg**2))), 4)

        sections.append({
            "section_type": 10,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "energy": round(energy, 4),
            "lufs": round(rms_db, 2),
            "spectral_centroid": round(spec_centroid, 2),
            "stem_energy": stem_energy,
        })

    return sections


def librosa_feature_spectral_centroid(
    y: np.ndarray,
    sr: int,
    n_fft: int,
    hop_length: int,
) -> np.ndarray:
    import librosa
    return librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length)[0]  # type: ignore[no-any-return]
