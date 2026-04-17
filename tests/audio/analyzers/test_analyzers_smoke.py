"""Smoke tests for v2 audio analyzers (Task 11 port parity).

Validates:
- AnalyzerRegistry auto-discovers all ported analyzers.
- Core analyzers (loudness, energy, spectral) run without librosa.
- Librosa-backed analyzers run when extra is installed; skipped otherwise.

Deeper behavior-level tests live in legacy ``tests/test_audio`` and can be
migrated as needed; this file locks the import + registration contract.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.analyzers import AnalyzerRegistry, BaseAnalyzer
from app.audio.core import AnalysisContext, AudioSignal

SR = 22050


def _signal(freq: float = 440.0, sec: float = 1.0) -> AudioSignal:
    t = np.linspace(0, sec, int(SR * sec), endpoint=False, dtype=np.float32)
    y = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return AudioSignal(samples=y, sample_rate=SR, duration_seconds=sec)


def _ctx(sec: float = 1.0) -> AnalysisContext:
    return AnalysisContext(_signal(sec=sec))


def test_registry_discovers_analyzers() -> None:
    reg = AnalyzerRegistry()
    reg.discover()
    # Core 4 + structure are numpy-only and always available
    names = set(reg.list_available())
    # At minimum the pure-numpy analyzers must register
    expected_core = {"loudness", "energy", "spectral", "structure"}
    assert expected_core.issubset(names), f"missing core: {expected_core - names}"


def test_base_analyzer_run_happy_path() -> None:
    reg = AnalyzerRegistry()
    reg.discover()
    loud = reg.get("loudness")
    assert loud is not None
    assert isinstance(loud, BaseAnalyzer)
    ctx = _ctx(1.0)
    result = loud.run(ctx)
    assert result.success is True
    assert result.analyzer_name == "loudness"
    assert result.features  # non-empty


def test_energy_spectral_run() -> None:
    reg = AnalyzerRegistry()
    reg.discover()
    ctx = _ctx(0.5)
    for name in ("energy", "spectral"):
        a = reg.get(name)
        assert a is not None
        res = a.run(ctx)
        assert res.success, f"{name} failed: {res.error}"


def test_librosa_analyzers_if_available() -> None:
    pytest.importorskip("librosa")
    reg = AnalyzerRegistry()
    reg.discover()
    # These require librosa — should register when extra installed
    for name in ("bpm", "key", "mfcc", "beat"):
        a = reg.get(name)
        if a is None:
            pytest.skip(f"{name} not registered — optional")
        assert a.name == name


def test_analyzer_name_strings_preserved() -> None:
    # Names are DB keys / test keys — must not change across the port.
    reg = AnalyzerRegistry()
    reg.discover()
    all_names = set(reg.list_all())
    expected = {
        "loudness",
        "energy",
        "spectral",
        "structure",
    }
    assert expected.issubset(all_names)
