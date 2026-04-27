"""Audit iter 11 (T-14): ``sequence_optimize(template='bogus')`` was
silently accepted. The tool's ``template`` parameter looked usable
but the call hardcoded ``template=None`` to the optimizer, so the
result was identical with and without the argument.

Now invalid template names raise ``ValidationError`` and valid ones
resolve to a real ``SetTemplateDefinition`` that the optimizer can
actually consume (template-aware fitness still gated on Phase 6 for
the GA, but at least the contract holds).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.errors import ValidationError
from app.tools.compute.sequence_optimize import sequence_optimize


def _mock_uow() -> MagicMock:
    """UoW with NO features — used for template-validation-only tests
    that fail fast before the features path is hit."""
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    return uow


def _mock_uow_with_features(track_ids: list[int]) -> MagicMock:
    """UoW with real-shape ``TrackFeatures`` for each id — used for
    success-path tests that need to reach the optimizer (audit iter
    48 / T-46 added an upfront missing-features guard)."""
    from app.shared.features import TrackFeatures

    feats = {tid: TrackFeatures(bpm=128.0 + i) for i, tid in enumerate(track_ids)}
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


@pytest.mark.asyncio
async def test_unknown_template_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match=r"unknown template 'bogus_template'"):
        await sequence_optimize(
            track_ids=[146, 147, 148],
            algorithm="greedy",
            template="bogus_template",
            uow=_mock_uow(),
            scorer=MagicMock(),
            optimizer_builder=MagicMock(),
        )


@pytest.mark.asyncio
async def test_known_template_passes_through_to_optimizer() -> None:
    """Sanity: a registered template name resolves and reaches the
    optimizer call as a real ``SetTemplateDefinition`` instance."""
    captured: dict[str, object] = {}

    def fake_optimizer_builder(*, algorithm: str, scorer: object) -> object:
        result = MagicMock()
        result.track_order = [146, 147, 148]
        result.quality_score = 0.5
        result.generations = 0

        def _optimize(**kwargs: object) -> object:
            captured.update(kwargs)
            return result

        return MagicMock(optimize=_optimize)

    await sequence_optimize(
        track_ids=[146, 147, 148],
        algorithm="greedy",
        template="classic_60",
        uow=_mock_uow_with_features([146, 147, 148]),
        scorer=MagicMock(),
        optimizer_builder=fake_optimizer_builder,
    )
    template_arg = captured.get("template")
    assert template_arg is not None
    assert getattr(template_arg, "name", None) == "classic_60"


@pytest.mark.asyncio
async def test_no_template_passes_none_through() -> None:
    """``template=None`` (default) passes through unchanged."""
    captured: dict[str, object] = {}

    def fake_optimizer_builder(*, algorithm: str, scorer: object) -> object:
        result = MagicMock()
        result.track_order = [146, 147, 148]
        result.quality_score = 0.5
        result.generations = 0

        def _optimize(**kwargs: object) -> object:
            captured.update(kwargs)
            return result

        return MagicMock(optimize=_optimize)

    await sequence_optimize(
        track_ids=[146, 147, 148],
        algorithm="greedy",
        uow=_mock_uow_with_features([146, 147, 148]),
        scorer=MagicMock(),
        optimizer_builder=fake_optimizer_builder,
    )
    assert captured.get("template") is None
