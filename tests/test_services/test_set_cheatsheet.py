from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.constants import NeuralMixCrossfaderFX
from app.services.set.cheatsheet import SetCheatSheetService
from app.transition.recipe import (
    EQPlan,
    RecipeStep,
    TransitionRecipe,
)


@pytest.mark.asyncio
async def test_get_cheat_sheet_falls_back_when_persisted_recipe_json_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_recipe = TransitionRecipe(
        fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP,
        bars=16,
        djay_tempo_adjust="sync",
        steps=(
            RecipeStep(bar=0, deck="B", action="Start B, bass killed"),
            RecipeStep(bar=8, deck="both", action="BASS SWAP on the one"),
        ),
        eq_plan=EQPlan(low="swap@bar8", mid="gradual", high="keep"),
        mix_in_section=None,
        mix_out_section=None,
        phrase_align=True,
        warnings=(),
        confidence=0.87,
        subgenre_modifier=None,
        rescue_move="filter sweep + hard cut",
    )
    calls: list[object] = []

    def _fake_build_recipe(*args, **kwargs):
        calls.append((args, kwargs))
        return expected_recipe

    monkeypatch.setattr(
        "app.transition.selector.TransitionSelector.build_recipe", _fake_build_recipe
    )

    svc = SetCheatSheetService(
        set_repo=SimpleNamespace(
            get_by_id=AsyncMock(return_value=SimpleNamespace(name="Night Set")),
            load_version_with_items=AsyncMock(
                return_value=(
                    SimpleNamespace(label="v1", quality_score=0.82),
                    [
                        SimpleNamespace(track_id=1, pinned=False),
                        SimpleNamespace(track_id=2, pinned=False),
                    ],
                )
            ),
        ),
        track_repo=SimpleNamespace(
            get_by_id=AsyncMock(
                side_effect=[
                    SimpleNamespace(title="Track A"),
                    SimpleNamespace(title="Track B"),
                ]
            ),
            get_by_ids=AsyncMock(
                return_value={
                    1: SimpleNamespace(title="Track A"),
                    2: SimpleNamespace(title="Track B"),
                }
            ),
        ),
        feature_repo=SimpleNamespace(
            get_scoring_features_batch=AsyncMock(
                return_value={
                    1: SimpleNamespace(
                        bpm=128.0, key_code=1, integrated_lufs=-8.0, mood="driving"
                    ),
                    2: SimpleNamespace(bpm=130.0, key_code=2, integrated_lufs=-7.0, mood="peak"),
                }
            )
        ),
        transition_repo=SimpleNamespace(
            get_score=AsyncMock(
                return_value=SimpleNamespace(
                    overall_quality=0.78,
                    transition_recipe_json="NOT VALID JSON {",
                    bpm_score=0.7,
                    harmonic_score=0.7,
                    energy_score=0.7,
                    spectral_score=0.7,
                    groove_score=0.7,
                    timbral_score=0.7,
                    hard_reject=False,
                    reject_reason=None,
                )
            )
        ),
    )

    text = await svc.get_cheat_sheet(set_id=1)

    assert calls
    assert "NEURAL MIX DRUM SWAP" in text
    assert "bar 8" in text
    assert "swap@bar8" in text
