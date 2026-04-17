"""AnalysisContext — eagerly-computed shared intermediates.

All STFT, magnitude, frequency bins, and frame energies are computed
once in __init__, then shared read-only across all analyzers.

Why eager, not lazy:
    Analyzers run in parallel via thread pool. Lazy properties would
    create check-then-act race conditions. Eager computation makes
    context immutable after construction — thread-safe by design.

Optional shared intermediates (e.g. onset envelopes) are computed
on first access under a lock so concurrent analyzers don't recompute
them. They're still safe to read after computation.

Memory: For 60s track at 22050 Hz: STFT ~4 MB, frame_energies ~10 KB.
"""

from __future__ import annotations

import threading

import numpy as np

from app.v2.audio.core.framing import compute_frame_energies
from app.v2.audio.core.rhythm import spectral_flux_onset_envelope
from app.v2.audio.core.spectral import compute_stft
from app.v2.audio.core.types import AudioSignal, FrameParams


class AnalysisContext:
    """Read-only shared computation context for a pipeline run.

    All properties are computed in __init__. Thread-safe: multiple
    analyzers can read from the same context concurrently.
    """

    __slots__ = (
        "_frame_energies",
        "_freqs",
        "_lock",
        "_magnitude",
        "_onset_env",
        "_params",
        "_signal",
        "_stft",
    )

    def __init__(
        self,
        signal: AudioSignal,
        params: FrameParams | None = None,
    ) -> None:
        self._signal = signal
        self._params = params or FrameParams()
        self._lock = threading.Lock()
        self._onset_env: np.ndarray | None = None

        self._stft: np.ndarray = compute_stft(
            signal.samples,
            self._params.frame_length,
            self._params.hop_length,
        )
        self._magnitude: np.ndarray = np.abs(self._stft)
        self._freqs: np.ndarray = np.fft.rfftfreq(
            self._params.frame_length,
            d=1.0 / signal.sample_rate,
        )
        self._frame_energies: np.ndarray = compute_frame_energies(
            signal.samples,
            self._params.frame_length,
            self._params.hop_length,
        )

    @property
    def samples(self) -> np.ndarray:
        return self._signal.samples

    @property
    def sr(self) -> int:
        return self._signal.sample_rate

    @property
    def duration(self) -> float:
        return self._signal.duration_seconds

    @property
    def file_path(self) -> str:
        return self._signal.file_path

    @property
    def params(self) -> FrameParams:
        return self._params

    @property
    def stft(self) -> np.ndarray:
        return self._stft

    @property
    def magnitude(self) -> np.ndarray:
        return self._magnitude

    @property
    def freqs(self) -> np.ndarray:
        return self._freqs

    @property
    def frame_energies(self) -> np.ndarray:
        return self._frame_energies

    def get_onset_env(self) -> np.ndarray:
        """Lazily compute and cache the shared onset envelope.

        Three analyzers (bpm, beat, tempogram) all need the same onset
        envelope. We keep the librosa availability contract, but compute the
        envelope from the already-materialized STFT to avoid unstable
        numba-accelerated librosa paths.
        """
        if self._onset_env is not None:
            return self._onset_env
        with self._lock:
            if self._onset_env is None:
                import librosa  # noqa: F401

                self._onset_env = spectral_flux_onset_envelope(
                    self._magnitude,
                    frame_energies=self._frame_energies,
                )
        return self._onset_env
