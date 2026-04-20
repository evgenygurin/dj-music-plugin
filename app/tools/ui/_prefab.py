"""Lazy ``prefab_ui`` re-exports.

Makes the ``fastmcp[apps]`` extra a soft dependency at import time: when
``prefab_ui`` is unavailable the component names resolve to ``None`` stubs
and ``HAS_PREFAB`` is ``False``. UI tools guard their Prefab branch on
``supports_ui(ctx)`` — which itself gates on ``HAS_PREFAB`` — so the
unresolved names are never touched at runtime in degraded environments.

Relies on ``from __future__ import annotations`` in every UI tool, so
``Column`` / ``Row`` / … appearing in signatures stay as string annotations
and don't explode module import when ``prefab_ui`` is missing.
"""

from __future__ import annotations

try:
    from prefab_ui.components import (
        Badge,
        Card,
        CardContent,
        CardHeader,
        CardTitle,
        Column,
        DataTable,
        DataTableColumn,
        Heading,
        Metric,
        Muted,
        Row,
    )
    from prefab_ui.components.charts import (
        BarChart,
        ChartSeries,
        LineChart,
        PieChart,
        RadarChart,
        RadialChart,
    )

    HAS_PREFAB = True
except ImportError:  # pragma: no cover — fastmcp[apps] extra missing
    HAS_PREFAB = False
    Badge = None  # type: ignore[assignment, misc]
    Card = None  # type: ignore[assignment, misc]
    CardContent = None  # type: ignore[assignment, misc]
    CardHeader = None  # type: ignore[assignment, misc]
    CardTitle = None  # type: ignore[assignment, misc]
    Column = None  # type: ignore[assignment, misc]
    DataTable = None  # type: ignore[assignment, misc]
    DataTableColumn = None  # type: ignore[assignment, misc]
    Heading = None  # type: ignore[assignment, misc]
    Metric = None  # type: ignore[assignment, misc]
    Muted = None  # type: ignore[assignment, misc]
    Row = None  # type: ignore[assignment, misc]
    BarChart = None  # type: ignore[assignment, misc]
    ChartSeries = None  # type: ignore[assignment, misc]
    LineChart = None  # type: ignore[assignment, misc]
    PieChart = None  # type: ignore[assignment, misc]
    RadarChart = None  # type: ignore[assignment, misc]
    RadialChart = None  # type: ignore[assignment, misc]


__all__ = [
    "HAS_PREFAB",
    "Badge",
    "BarChart",
    "Card",
    "CardContent",
    "CardHeader",
    "CardTitle",
    "ChartSeries",
    "Column",
    "DataTable",
    "DataTableColumn",
    "Heading",
    "LineChart",
    "Metric",
    "Muted",
    "PieChart",
    "RadarChart",
    "RadialChart",
    "Row",
]
