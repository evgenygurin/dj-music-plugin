from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class InharmonicityAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "inharmonicity"
    level: ClassVar[int] = 6
    required_packages: ClassVar[list[str]] = ["essentia"]

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, float | None]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"inharmonicity": None}

        try:
            frame_size = 4096
            hop_size = 2048
            w = es.Windowing(type="hann")
            spectrum = es.Spectrum()
            spectral_peaks = es.SpectralPeaks(maxPeaks=100)
            inharmonicity_algo = es.Inharmonicity()

            values: list[float] = []
            for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
                spec = spectrum(w(frame))
                freqs, mags = spectral_peaks(spec)
                if len(freqs) >= 2:
                    values.append(float(inharmonicity_algo(freqs, mags)))

            mean_val = float(np.mean(values)) if values else None
            return {"inharmonicity": mean_val}
        except Exception:
            return {"inharmonicity": None}

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        return self.analyze(ctx.samples.astype(np.float32, copy=False), ctx.sr)
