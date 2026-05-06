"""Per-component scoring functions for the transition scorer.

Each module exposes a single ``score_<component>`` pure function that
takes two ``TrackFeatures`` and returns a float in [0, 1]. The
orchestrator (``app/domain/transition/scorer.py``) calls them and
combines the results with weights from ``weights.py``.

Post Neural Mix refactor only ``score_bpm`` and ``score_energy`` live
here; the four stem-aware components (drums / bass / harmonics /
vocals) are computed inside ``app/domain/transition/neural_mix.py``.

No I/O, no DB, no class state — these are leaf functions for the
weighted sum.
"""

from app.domain.transition.components.bpm import score_bpm
from app.domain.transition.components.energy import score_energy

__all__ = [
    "score_bpm",
    "score_energy",
]
