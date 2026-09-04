"""Pure declarative configuration domain."""

from .profile import TransitionProfile
from .provenance import Provenance
from .resolver import (
    ConfigResolver,
    EffectiveConfiguration,
    LegacyConfigAdapter,
    ResolvedTransitionConfig,
)
from .schema import ParameterClass, ParameterDefinition, TransitionSchema

__all__ = [
    "ConfigResolver",
    "EffectiveConfiguration",
    "LegacyConfigAdapter",
    "ParameterClass",
    "ParameterDefinition",
    "Provenance",
    "ResolvedTransitionConfig",
    "TransitionProfile",
    "TransitionSchema",
]
