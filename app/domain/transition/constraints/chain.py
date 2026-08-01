from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.shared.features import TrackFeatures

if TYPE_CHECKING:
    from app.domain.transition.score import TransitionScore


class HardConstraintChain:
    def __init__(self, constraints: tuple[Any, ...]) -> None:
        self._constraints = constraints

    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> TransitionScore | None:
        for c in self._constraints:
            result = c.check(
                from_t,
                to_t,
                pre_bpm_dist=pre_bpm_dist,
                pre_key_dist=pre_key_dist,
                pre_energy_delta=pre_energy_delta,
            )
            if isinstance(result, tuple):
                reason, _warning = result
            else:
                reason = result
            if reason is not None:
                from app.domain.transition.score import TransitionScore

                return TransitionScore(
                    bpm=0.0,
                    energy=0.0,
                    drums=0.0,
                    bass=0.0,
                    harmonics=0.0,
                    vocals=0.0,
                    overall=0.0,
                    hard_reject=True,
                    reject_reason=reason,
                )
        return None
