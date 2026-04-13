"""Beat detector — librosa-based rhythm analysis with downbeat detection.

Computes: onset_rate, pulse_clarity, kick_prominence, hp_ratio,
beat_times, downbeat_times, first_downbeat_ms, downbeat_confidence.

Beat detection uses librosa.beat.beat_track() for metrically regular
beat positions (quarter notes in 4/4 time), with octave error correction
via tempo_from_onset_autocorrelation() as BPM hint.

Downbeat detection finds beat 1 of each bar using multi-feature analysis
based on QM University spectral difference approach (ISMIR research):
- Beat-synchronous mel spectrogram difference (timbral changes at bar boundaries)
- Chroma novelty (harmonic changes at bar boundaries)
- Low-mid frequency energy patterns (bass emphasis on beat 1)

Performance notes:
    Kick prominence uses onset-weighted STFT power (no HPSS needed).
    Pulse clarity uses FFT-based global autocorrelation of the onset
    envelope (~10x faster than full tempogram).
    Onset envelope is shared via ctx.get_onset_env() (bpm/tempogram reuse it).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.rhythm import tempo_from_onset_autocorrelation


def _autocorrelation_peak(onset_env: np.ndarray, min_lag: int, max_lag: int) -> float:
    """Compute the dominant autocorrelation peak in a lag range.

    Used as a pulse-clarity proxy: the strength of the strongest
    periodic component in the onset envelope, normalized by lag-0
    autocorrelation (which equals the signal energy).

    Result is clamped to [0, 1].
    """
    n = len(onset_env)
    if n < max_lag + 1 or max_lag <= min_lag:
        return 0.0

    centered = onset_env - float(np.mean(onset_env))
    nfft = 1 << (2 * n - 1).bit_length()
    spec = np.fft.rfft(centered, nfft)
    acf = np.fft.irfft(spec * np.conj(spec), nfft)[:n]
    if acf[0] <= 0:
        return 0.0

    peak_in_range = float(np.max(acf[min_lag : max_lag + 1]))
    return float(max(0.0, min(1.0, peak_in_range / acf[0])))


@register_analyzer
class BeatDetector(BaseAnalyzer):
    """Rhythm analysis: beat tracking, downbeat detection, onset rate, kick prominence."""

    name: ClassVar[str] = "beat"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm", "beat"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Analyze rhythmic features with metrically regular beats and downbeat detection.

        Uses librosa.beat.beat_track() with BPM hint from onset autocorrelation
        for metrically regular beats, NOT find_peaks() which returns irregular onsets.
        """
        import librosa

        sr = ctx.sr
        analysis_duration = ctx.duration
        samples = ctx.samples

        # --- Onset envelope + tempo estimation (shared via ctx) ---
        onset_env = ctx.get_onset_env()
        tempo_est = tempo_from_onset_autocorrelation(onset_env, sr, ctx.params.hop_length)
        corrected_bpm = tempo_est.bpm

        # --- Metrically regular beat detection ---
        # beat_track() with BPM hint returns tempo-aligned quarter notes,
        # unlike find_peaks() which returns irregular onset events.
        _tempo, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_env,
            sr=sr,
            bpm=corrected_bpm,
            hop_length=ctx.params.hop_length,
            units="frames",
        )
        beat_times: list[float] = (
            beat_frames.astype(np.float64) * ctx.params.hop_length / sr
        ).tolist()

        # --- Onset rate (from onset peaks, not beat grid) ---
        from app.audio.core.rhythm import find_beat_times

        onsets = find_beat_times(onset_env, sr, ctx.params.hop_length, bpm_hint=corrected_bpm)
        onset_rate = float(len(onsets) / analysis_duration) if analysis_duration > 0 else 0.0

        # --- Pulse clarity via FFT autocorrelation ---
        hop_seconds = ctx.params.hop_length / sr
        if hop_seconds > 0 and len(onset_env) > 4:
            min_lag = max(1, int((60.0 / 200.0) / hop_seconds))
            max_lag = min(len(onset_env) - 1, int((60.0 / 60.0) / hop_seconds))
            pulse_clarity = _autocorrelation_peak(onset_env, min_lag, max_lag)
        else:
            pulse_clarity = 0.0

        # --- HP ratio (from magnitude spectrum) ---
        steady_mag = np.mean(ctx.magnitude, axis=1)
        transient_mag = np.maximum(
            np.diff(ctx.magnitude, axis=1, prepend=ctx.magnitude[:, :1]),
            0.0,
        )
        h_energy = float(np.sum(steady_mag**2) * max(1, ctx.magnitude.shape[1]))
        p_energy = float(np.sum(transient_mag**2))
        hp_ratio = float(np.sqrt(h_energy / (p_energy + 1e-10)))

        # --- Kick prominence (onset-weighted low-band energy) ---
        low_mask = ctx.freqs < 200.0
        onset_weight_sum = float(np.sum(onset_env))
        if np.any(low_mask) and onset_weight_sum > 0:
            onset_weights = onset_env / onset_weight_sum
            weighted_power = (ctx.magnitude**2) * onset_weights[np.newaxis, :]
            weighted_total = float(np.sum(weighted_power))
            low_perc_energy = float(np.sum(weighted_power[low_mask, :]))
            kick_prominence = low_perc_energy / max(weighted_total, 1e-10)
        else:
            kick_prominence = 0.0

        # --- Downbeat detection (beat 1 of each bar) ---
        downbeat_phase, downbeat_conf = _find_downbeat_phase(
            beat_times=beat_times,
            beat_frames=beat_frames,
            samples=samples,
            sr=sr,
            magnitude=ctx.magnitude,
            freqs=ctx.freqs,
        )

        n_beats = len(beat_times)
        downbeat_times = [beat_times[i] for i in range(downbeat_phase, n_beats, 4)]
        first_downbeat_ms = round(downbeat_times[0] * 1000, 1) if downbeat_times else 0.0

        beats_intervals = (
            [beat_times[i + 1] - beat_times[i] for i in range(n_beats - 1)] if n_beats > 1 else []
        )

        return {
            "onset_rate": round(onset_rate, 4),
            "pulse_clarity": round(pulse_clarity, 4),
            "kick_prominence": round(kick_prominence, 4),
            "hp_ratio": round(hp_ratio, 4),
            "beat_times": beat_times,
            "downbeat_times": downbeat_times,
            "first_downbeat_ms": first_downbeat_ms,
            "downbeat_confidence": round(downbeat_conf, 4),
            "beats_intervals": beats_intervals,
        }


def _find_downbeat_phase(
    *,
    beat_times: list[float],
    beat_frames: np.ndarray,
    samples: np.ndarray,
    sr: int,
    magnitude: np.ndarray,
    freqs: np.ndarray,
) -> tuple[int, float]:
    """Determine which phase offset (0-3) corresponds to beat 1 of each bar.

    Three complementary features (ISMIR research + QM BarBeatTrack approach):

    1. **Beat-sync mel spectrogram difference** (weight 0.40) — average mel
       spectrogram between consecutive beats, then cosine distance. Bar
       boundaries have highest spectral change.

    2. **Chroma novelty** (weight 0.35) — harmonic content changes most
       at bar boundaries.

    3. **Low-mid energy 100-500 Hz** (weight 0.25) — bass lines emphasize
       beat 1 with root notes.
    """
    import librosa

    n_beats = len(beat_times)
    if n_beats < 8:
        return 0, 0.0

    # Feature 1: Beat-synchronous mel spectrogram spectral difference
    mel_spec = librosa.feature.melspectrogram(y=samples, sr=sr)
    beat_frame_list: list[int] = beat_frames.tolist()
    beat_sync_mel = librosa.util.sync(mel_spec, beat_frame_list, aggregate=np.mean)

    mel_diff = np.zeros(n_beats)
    n_sync_cols = beat_sync_mel.shape[1]
    for i in range(1, min(n_beats, n_sync_cols)):
        a = beat_sync_mel[:, i]
        b = beat_sync_mel[:, i - 1]
        norms_product = np.linalg.norm(a) * np.linalg.norm(b)
        if norms_product > 1e-10:
            mel_diff[i] = 1.0 - float(np.dot(a, b)) / norms_product

    # Feature 2: Chroma novelty
    chroma = librosa.feature.chroma_cqt(y=samples, sr=sr)
    beat_sync_chroma = librosa.util.sync(chroma, beat_frame_list, aggregate=np.mean)

    chroma_novelty = np.zeros(n_beats)
    n_sync_chroma = beat_sync_chroma.shape[1]
    for i in range(1, min(n_beats, n_sync_chroma)):
        a = beat_sync_chroma[:, i]
        b = beat_sync_chroma[:, i - 1]
        norms_product = np.linalg.norm(a) * np.linalg.norm(b)
        if norms_product > 1e-10:
            chroma_novelty[i] = 1.0 - float(np.dot(a, b)) / norms_product

    # Feature 3: Low-mid frequency energy (reuse precomputed magnitude)
    bass_mask = (freqs >= 100) & (freqs < 500)
    bass_energy = np.sum(magnitude[bass_mask, :] ** 2, axis=0)
    max_stft_frame = len(bass_energy) - 1
    bass_at_beats = bass_energy[np.clip(beat_frames, 0, max_stft_frame)]

    # Normalize and combine
    mel_diff_norm = _safe_normalize(mel_diff)
    chroma_norm = _safe_normalize(chroma_novelty)
    bass_norm = _safe_normalize(bass_at_beats)

    accent = 0.40 * mel_diff_norm + 0.35 * chroma_norm + 0.25 * bass_norm

    # Score each of 4 phase offsets
    phase_scores: list[float] = []
    for phase in range(4):
        indices = list(range(phase, n_beats, 4))
        if len(indices) < 2:
            phase_scores.append(0.0)
            continue
        phase_scores.append(float(np.mean(accent[indices])))

    best_phase = int(np.argmax(phase_scores))

    sorted_scores = sorted(phase_scores, reverse=True)
    denom = sorted_scores[0] + 1e-10
    confidence = min(1.0, (sorted_scores[0] - sorted_scores[1]) / denom)

    return best_phase, confidence


def _safe_normalize(x: np.ndarray) -> np.ndarray:
    """Normalize array to [0, 1]. Returns zeros if range is negligible."""
    mn, mx = float(x.min()), float(x.max())
    rng = mx - mn
    if rng < 1e-10:
        return np.zeros_like(x, dtype=np.float64)
    return (x - mn) / rng
