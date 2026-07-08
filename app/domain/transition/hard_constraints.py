"""Hard-constraint gate for transition scoring.

Thin adapter — delegates to ``constraints.chain.HardConstraintChain``.
"""

from __future__ import annotations

from app.domain.transition.constraints.chain import HardConstraintChain
from app.domain.transition.constraints.specs.bpm_difference import BpmDifferenceSpec
from app.domain.transition.constraints.specs.camelot_distance import CamelotDistanceSpec
from app.domain.transition.constraints.specs.energy_gap import EnergyGapSpec
from app.domain.transition.key_utils import key_reliable
from app.domain.transition.score import TransitionScore
from app.shared.features import TrackFeatures

_chain = HardConstraintChain((BpmDifferenceSpec(), CamelotDistanceSpec(), EnergyGapSpec()))


def check_hard_constraints(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    pre_bpm_dist: float | None = None,
    pre_key_dist: int | None = None,
    pre_energy_delta: float | None = None,
) -> TransitionScore | None:
    """Return a zero-score rejection or ``None`` if all constraints pass."""
    return _chain.check(
        from_t,
        to_t,
        pre_bpm_dist=pre_bpm_dist,
        pre_key_dist=pre_key_dist,
        pre_energy_delta=pre_energy_delta,
    )


__all__ = ["check_hard_constraints", "key_reliable"]
