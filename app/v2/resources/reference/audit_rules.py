"""Audit rules reference resource.

URI: ``reference://audit_rules``

Emits the default Chain-of-Responsibility audit rules and the
``AuditSettings`` thresholds each one consumes. Payload built lazily on
first access because ``AuditSettings`` reads env vars; computing it at
import time would freeze values before user ``.env`` is loaded.
"""

from __future__ import annotations

from typing import Any

from fastmcp.resources import resource

from app.v2.config import get_settings
from app.v2.domain.audit.rules import DEFAULT_AUDIT_RULES
from app.v2.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.v2.schemas.resource_views import (
    AuditRulesView,
    AuditRuleView,
)

# Map concrete rule class name -> (issue id, severity, [AuditSettings field names])
# Mirrors the bodies of rules in app.v2.domain.audit.rules.
_RULE_METADATA: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "BpmRangeRule": ("bpm_out_of_range", "warning", ("techno_bpm_min", "techno_bpm_max")),
    "LufsRangeRule": (
        "lufs_out_of_range",
        "warning",
        ("techno_lufs_min", "techno_lufs_max"),
    ),
    "ClippingRiskRule": ("clipping_risk", "warning", ("audit_true_peak_max",)),
    "UnreliableBpmRule": ("unreliable_bpm", "warning", ("audit_bpm_confidence_min",)),
    "UnreliableKeyRule": ("unreliable_key", "warning", ("audit_key_confidence_min",)),
    "VariableTempoRule": ("variable_tempo", "info", ()),
    "TooHarmonicRule": ("too_harmonic", "warning", ("audit_hp_ratio_max",)),
    "ExcessiveDynamicsRule": (
        "excessive_dynamics",
        "warning",
        ("audit_crest_factor_max",),
    ),
    "NoiseSpectrumRule": (
        "noise_spectrum",
        "warning",
        ("audit_spectral_flatness_max",),
    ),
}


def _build_payload() -> AuditRulesView:
    settings = get_settings()
    audit = settings.audit
    rules: list[AuditRuleView] = []
    for rule in DEFAULT_AUDIT_RULES:
        class_name = rule.__class__.__name__
        issue, severity, fields = _RULE_METADATA.get(class_name, ("unknown", "info", ()))
        thresholds: dict[str, Any] = {field: getattr(audit, field) for field in fields}
        rules.append(
            AuditRuleView(
                name=class_name,
                severity=severity,
                issue=issue,
                thresholds=thresholds,
            )
        )
    return AuditRulesView(total=len(rules), rules=rules)


@resource(
    "reference://audit_rules",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:audit_rules"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def reference_audit_rules() -> str:
    """Default techno-audit rules with their current threshold values."""
    return _build_payload().model_dump_json()
