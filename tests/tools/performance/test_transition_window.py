from __future__ import annotations

import pytest

from app.domain.performance.cue_points import TransitionCueWindow
from app.tools.performance import transition_window as mod


class _SectionRepo:
    async def list_by_track(self, track_id: int) -> list[object]:
        return []


class _FeatureRepo:
    async def get_by_track_id(self, track_id: int) -> object:
        return type("Features", (), {"bpm": 128.0})()


class _Uow:
    track_sections = _SectionRepo()
    track_features = _FeatureRepo()


@pytest.mark.asyncio
async def test_transition_window_passes_preferred_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    def fake_find_transition_window(
        from_sections: list[dict],
        to_sections: list[dict],
        bpm: float,
        preferred_bars: int = 32,
    ) -> TransitionCueWindow:
        captured["preferred_bars"] = preferred_bars
        return TransitionCueWindow(1, 2, 0, 1, 0, 1, f"Transition: {preferred_bars} bars")

    monkeypatch.setattr(mod, "find_transition_window", fake_find_transition_window)

    result = await mod.transition_window(
        from_track_id=1,
        to_track_id=2,
        bpm=128.0,
        preferred_bars=16,
        uow=_Uow(),
    )

    assert captured == {"preferred_bars": 16}
    assert result.recommendation == "Transition: 16 bars"
