"""Audit rules — Chain of Responsibility for playlist quality checks (v2).

Each rule checks one aspect of audio quality and returns a list of issues.
Pure domain logic: no I/O, no DB access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.v2.config import get_settings


@dataclass(frozen=True)
class AuditIssue:
    """A single quality issue found by an audit rule."""

    track_id: int
    title: str
    issue: str
    severity: str  # "error" | "warning" | "info"
    detail: str | None = None


class AuditRule(Protocol):
    """Protocol for audit rules — Chain of Responsibility pattern."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        """Check features and return any issues found."""
        ...


class BpmRangeRule:
    """Check BPM is within techno range."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        settings = get_settings()
        if features.bpm is None:
            return []
        if (
            features.bpm < settings.audit.techno_bpm_min
            or features.bpm > settings.audit.techno_bpm_max
        ):
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="bpm_out_of_range",
                    severity="warning",
                    detail=(
                        f"BPM {features.bpm:.1f} outside "
                        f"[{settings.audit.techno_bpm_min}-{settings.audit.techno_bpm_max}]"
                    ),
                )
            ]
        return []


class LufsRangeRule:
    """Check LUFS is within techno range."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        settings = get_settings()
        if features.integrated_lufs is None:
            return []
        if (
            features.integrated_lufs < settings.audit.techno_lufs_min
            or features.integrated_lufs > settings.audit.techno_lufs_max
        ):
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="lufs_out_of_range",
                    severity="warning",
                    detail=(
                        f"LUFS {features.integrated_lufs:.1f} outside "
                        f"[{settings.audit.techno_lufs_min}-{settings.audit.techno_lufs_max}]"
                    ),
                )
            ]
        return []


class ClippingRiskRule:
    """Check for clipping risk via true peak."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        settings = get_settings()
        if features.true_peak_db is None:
            return []
        if features.true_peak_db > settings.audit.audit_true_peak_max:
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="clipping_risk",
                    severity="warning",
                    detail=(
                        f"True peak {features.true_peak_db:.1f} dB"
                        f" > {settings.audit.audit_true_peak_max} dB"
                    ),
                )
            ]
        return []


class UnreliableBpmRule:
    """Check BPM detection confidence."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        settings = get_settings()
        if features.bpm_confidence is None:
            return []
        if features.bpm_confidence < settings.audit.audit_bpm_confidence_min:
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="unreliable_bpm",
                    severity="warning",
                    detail=(
                        f"BPM confidence {features.bpm_confidence:.2f}"
                        f" < {settings.audit.audit_bpm_confidence_min}"
                    ),
                )
            ]
        return []


class UnreliableKeyRule:
    """Check key detection confidence."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        settings = get_settings()
        if features.key_confidence is None:
            return []
        if features.key_confidence < settings.audit.audit_key_confidence_min:
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="unreliable_key",
                    severity="warning",
                    detail=(
                        f"Key confidence {features.key_confidence:.2f}"
                        f" < {settings.audit.audit_key_confidence_min}"
                    ),
                )
            ]
        return []


class VariableTempoRule:
    """Flag tracks with variable tempo."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        if features.variable_tempo is True:
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="variable_tempo",
                    severity="info",
                    detail="Variable tempo - harder to beatmatch",
                )
            ]
        return []


class TooHarmonicRule:
    """Check harmonic-to-percussive ratio isn't too high for techno."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        settings = get_settings()
        if features.hp_ratio is None:
            return []
        if features.hp_ratio > settings.audit.audit_hp_ratio_max:
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="too_harmonic",
                    severity="warning",
                    detail=(
                        f"HP ratio {features.hp_ratio:.1f}"
                        f" > {settings.audit.audit_hp_ratio_max} (too harmonic for techno)"
                    ),
                )
            ]
        return []


class ExcessiveDynamicsRule:
    """Check crest factor isn't too high."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        settings = get_settings()
        if features.crest_factor_db is None:
            return []
        if features.crest_factor_db > settings.audit.audit_crest_factor_max:
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="excessive_dynamics",
                    severity="warning",
                    detail=(
                        f"Crest factor {features.crest_factor_db:.1f} dB"
                        f" > {settings.audit.audit_crest_factor_max} dB"
                    ),
                )
            ]
        return []


class NoiseSpectrumRule:
    """Check spectral flatness isn't too high (noise-like)."""

    def check(self, track_id: int, title: str, features: Any) -> list[AuditIssue]:
        settings = get_settings()
        if features.spectral_flatness is None:
            return []
        if features.spectral_flatness > settings.audit.audit_spectral_flatness_max:
            return [
                AuditIssue(
                    track_id=track_id,
                    title=title,
                    issue="noise_spectrum",
                    severity="warning",
                    detail=(
                        f"Spectral flatness {features.spectral_flatness:.2f}"
                        f" > {settings.audit.audit_spectral_flatness_max}"
                    ),
                )
            ]
        return []


# Default chain — all 9 rules in order
DEFAULT_AUDIT_RULES: list[AuditRule] = [
    BpmRangeRule(),
    LufsRangeRule(),
    ClippingRiskRule(),
    UnreliableBpmRule(),
    UnreliableKeyRule(),
    VariableTempoRule(),
    TooHarmonicRule(),
    ExcessiveDynamicsRule(),
    NoiseSpectrumRule(),
]


def run_audit_rules(
    rules: list[AuditRule],
    track_id: int,
    title: str,
    features: Any,
) -> list[AuditIssue]:
    """Run all rules against a track's features, collecting all issues."""
    issues: list[AuditIssue] = []
    for rule in rules:
        issues.extend(rule.check(track_id, title, features))
    return issues
