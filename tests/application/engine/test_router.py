from dataclasses import dataclass

from pytest import approx

from app.application.engine.mode import EngineMode, EngineSelection
from app.application.engine.router import TransitionEngineRouter


@dataclass(frozen=True)
class Result:
    candidate: str
    score: float


def test_router_uses_legacy_by_default() -> None:
    router = TransitionEngineRouter(
        EngineSelection.from_values(None, None),
        legacy=lambda: Result("legacy", 0.7),
        new=lambda: Result("new", 0.8),
    )

    result = router.run()

    assert result.value == Result("legacy", 0.7)
    assert result.comparison is None


def test_router_shadow_returns_new_result_and_parity_diagnostics() -> None:
    router = TransitionEngineRouter(
        EngineSelection(EngineMode.SHADOW, "legacy"),
        legacy=lambda: Result("same", 0.7),
        new=lambda: Result("same", 0.8),
        compare=lambda legacy, new: {
            "candidate_parity": legacy.candidate == new.candidate,
            "score_delta": new.score - legacy.score,
        },
    )

    result = router.run()

    assert result.value == Result("same", 0.8)
    assert result.comparison is not None
    assert result.comparison["candidate_parity"] is True
    assert result.comparison["score_delta"] == approx(0.1)


def test_router_rejects_missing_new_engine_for_new_mode() -> None:
    router = TransitionEngineRouter(
        EngineSelection(EngineMode.NEW, "new"),
        legacy=lambda: Result("legacy", 0.7),
    )

    try:
        router.run()
    except RuntimeError as exc:
        assert "new engine" in str(exc)
    else:
        raise AssertionError("expected missing new engine failure")
