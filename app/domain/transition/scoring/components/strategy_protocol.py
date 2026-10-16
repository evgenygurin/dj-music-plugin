"""Strategy Protocol для scoring components (GoF Strategy)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.shared.features import TrackFeatures


@runtime_checkable
class ScoringComponent(Protocol):
    """Strategy interface для scoring component."""

    name: str

    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float: ...
    def score_pairs(
        self, fa: FeatureArrays, ia: npt.NDArray[np.int64], ib: npt.NDArray[np.int64]
    ) -> npt.NDArray[np.float64]: ...
