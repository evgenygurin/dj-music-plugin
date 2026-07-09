from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from app.audio.deep.structure_analyzer import analyze_structure


def test_analyze_structure_returns_list_of_sections(tmp_path: Path) -> None:
    sr = 44100
    signal = np.random.default_rng(42).random(sr * 3).astype(np.float32) * 0.3
    audio_path = tmp_path / "test.wav"
    sf.write(str(audio_path), signal, sr)

    stems = {}
    for name in ("vocals", "drums", "bass", "other"):
        sp = tmp_path / f"{name}.wav"
        sf.write(str(sp), signal * 0.5, sr)
        stems[name] = sp

    result = analyze_structure(audio_path, stems)

    assert isinstance(result, list)
    if result:
        section = result[0]
        assert "section_type" in section
        assert "start_ms" in section
        assert "end_ms" in section
        assert "lufs" in section or section.get("lufs") is None
        assert "stem_energy" in section


def test_analyze_structure_empty_on_silence(tmp_path: Path) -> None:
    sr = 44100
    signal = np.zeros(sr).astype(np.float32)
    audio_path = tmp_path / "silence.wav"
    sf.write(str(audio_path), signal, sr)

    result = analyze_structure(audio_path, {})
    assert isinstance(result, list)
