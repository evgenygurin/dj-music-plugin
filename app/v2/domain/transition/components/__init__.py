"""Per-component scoring functions for the transition scorer.

Each module exposes a single ``score_<component>`` pure function that
takes two ``TrackFeatures`` and returns a float in [0, 1]. The
orchestrator (``app/transition/scorer.py``) calls them and
combines the results with weights from ``weights.py``.

No I/O, no DB, no class state — these are leaf functions for the
weighted sum.
"""

from app.v2.domain.transition.components.bpm import score_bpm
from app.v2.domain.transition.components.energy import score_energy
from app.v2.domain.transition.components.groove import score_groove
from app.v2.domain.transition.components.harmonic import score_harmonic
from app.v2.domain.transition.components.spectral import score_spectral
from app.v2.domain.transition.components.timbral import score_timbral

__all__ = [
    "score_bpm",
    "score_energy",
    "score_groove",
    "score_harmonic",
    "score_spectral",
    "score_timbral",
]
