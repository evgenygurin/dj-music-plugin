"""Per-component scoring functions for the transition scorer.

Each module exposes a single ``score_<component>`` pure function that
takes two ``TrackFeatures`` and returns a float in [0, 1]. The
orchestrator (``app/transition/scorer.py``) calls them and
combines the results with weights from ``weights.py``.

No I/O, no DB, no class state — these are leaf functions for the
weighted sum.
"""

from dj_music.transition.components.bpm import score_bpm
from dj_music.transition.components.energy import score_energy
from dj_music.transition.components.groove import score_groove
from dj_music.transition.components.harmonic import score_harmonic
from dj_music.transition.components.spectral import score_spectral
from dj_music.transition.components.timbral import score_timbral

__all__ = [
    "score_bpm",
    "score_energy",
    "score_groove",
    "score_harmonic",
    "score_spectral",
    "score_timbral",
]
