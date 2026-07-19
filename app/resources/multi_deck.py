"""Multi-deck toolkit resources: feature catalog + section type reference.

URIs:
    reference://feature-catalog/stem_features
    reference://section-types
"""

from __future__ import annotations

import json

from fastmcp.resources import resource

from app.resources._feature_catalog import STEM_FEATURE_CATALOG
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META

SECTION_TYPES: dict[int, dict[str, str]] = {
    0: {"name": "intro", "label": "Intro", "description": "Вступление без кика."},
    1: {"name": "buildup", "label": "Buildup", "description": "Нарастание энергии к дропу."},
    2: {"name": "drop", "label": "Drop", "description": "Основная секция с полным киком и басом."},
    3: {"name": "breakdown", "label": "Breakdown", "description": "Спад энергии, снятие кика."},
    4: {"name": "bridge", "label": "Bridge", "description": "Переходная секция."},
    5: {
        "name": "drop_variation",
        "label": "Drop Variation",
        "description": "Вариация основного дропа.",
    },
    6: {"name": "outro", "label": "Outro", "description": "Завершение, затухание."},
    7: {"name": "fill", "label": "Fill", "description": "Брейк/заполнение, короткая вставка."},
    8: {
        "name": "drum_only",
        "label": "Drum Only",
        "description": "Только ударные, без баса и синтов.",
    },
    9: {
        "name": "ambient",
        "label": "Ambient",
        "description": "Атмосферная секция, пэды и текстуры.",
    },
    10: {"name": "acid_line", "label": "Acid Line", "description": "Кислотная линия TB-303."},
    11: {"name": "unknown", "label": "Unknown", "description": "Неклассифицированная секция."},
}


@resource(
    "reference://feature-catalog/stem_features",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:feature_catalog"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
def stem_features_catalog() -> str:
    """Feature catalog for stem_features entity — 44 field descriptions."""
    return json.dumps(
        {
            "entity": "stem_features",
            "total_fields": len(STEM_FEATURE_CATALOG),
            "fields": [{"name": name, **entry} for name, entry in STEM_FEATURE_CATALOG.items()],
        },
        ensure_ascii=False,
    )


@resource(
    "reference://section-types",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:section_types"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
def section_types() -> str:
    """TrackSection type enum (0-11). Mirrors SectionType in models."""
    return json.dumps(
        {
            "description": "TrackSection type enum (0-11). Mirrors SectionType in models.",
            "types": [{"value": code, **info} for code, info in SECTION_TYPES.items()],
        },
        ensure_ascii=False,
    )
