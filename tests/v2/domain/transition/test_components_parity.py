"""Numeric parity: v2 components produce the same scores as legacy."""

from __future__ import annotations

import pytest

from app.v2.domain.transition.components import (
    score_bpm as v2_bpm,
)
from app.v2.domain.transition.components import (
    score_energy as v2_energy,
)
from app.v2.domain.transition.components import (
    score_groove as v2_groove,
)
from app.v2.domain.transition.components import (
    score_harmonic as v2_harmonic,
)
from app.v2.domain.transition.components import (
    score_spectral as v2_spectral,
)
from app.v2.domain.transition.components import (
    score_timbral as v2_timbral,
)
from app.v2.domain.transition.features import TrackFeatures as V2Features

_FEATURES = dict(
    bpm=128.0,
    key_code=5,
    integrated_lufs=-8.0,
    energy_mean=0.3,
    spectral_centroid_hz=3000.0,
    onset_rate=5.0,
    kick_prominence=0.5,
    hnr_db=10.0,
    chroma_entropy=0.6,
)


@pytest.mark.parametrize(
    ("legacy_path", "v2_fn_name", "v2_fn"),
    [
        ("app.transition.components.bpm:score_bpm", "score_bpm", v2_bpm),
        ("app.transition.components.harmonic:score_harmonic", "score_harmonic", v2_harmonic),
        ("app.transition.components.energy:score_energy", "score_energy", v2_energy),
        ("app.transition.components.spectral:score_spectral", "score_spectral", v2_spectral),
        ("app.transition.components.groove:score_groove", "score_groove", v2_groove),
        ("app.transition.components.timbral:score_timbral", "score_timbral", v2_timbral),
    ],
)
def test_component_parity(legacy_path: str, v2_fn_name: str, v2_fn) -> None:
    mod_path, fn_name = legacy_path.split(":")
    legacy_mod = __import__(mod_path, fromlist=[fn_name])
    legacy_fn = getattr(legacy_mod, fn_name)
    from app.entities.audio.features import TrackFeatures as LegacyFeatures

    a_legacy = LegacyFeatures(**_FEATURES)
    b_legacy = LegacyFeatures(**{**_FEATURES, "bpm": 130.0, "key_code": 7})
    a_v2 = V2Features(**_FEATURES)
    b_v2 = V2Features(**{**_FEATURES, "bpm": 130.0, "key_code": 7})

    legacy_score = legacy_fn(a_legacy, b_legacy)
    v2_score = v2_fn(a_v2, b_v2)
    assert legacy_score == pytest.approx(v2_score, abs=1e-9), (
        f"{v2_fn_name} parity drift: legacy={legacy_score}, v2={v2_score}"
    )
