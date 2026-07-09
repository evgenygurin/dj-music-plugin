from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domain.transition.score import TransitionScore

if TYPE_CHECKING:
    from app.domain.transition.intent import TransitionIntent
    from app.domain.transition.section_context import SectionContext
    from app.shared.features import TrackFeatures


class CompositeScorer:
    def __init__(
        self,
        components: tuple[Any, ...],
        overlays: tuple[Any, ...] = (),
    ) -> None:
        self._components = components
        self._overlays = overlays

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        scores: dict[str, float] = {}
        for comp in self._components:
            scores[comp.name] = comp.score(from_t, to_t)

        weights = {comp.name: comp.default_weight for comp in self._components}
        for overlay in self._overlays:
            weights = overlay.apply(weights, intent=intent, section_context=section_context)

        overall = sum(scores[name] * weights.get(name, 0.0) for name in scores)

        return TransitionScore(
            bpm=scores.get("bpm", 0.0),
            energy=scores.get("energy", 0.0),
            drums=scores.get("drums", 0.0),
            bass=scores.get("bass", 0.0),
            harmonics=scores.get("harmonics", 0.0),
            vocals=scores.get("vocals", 0.0),
            overall=max(0.0, min(1.0, overall)),
        )
