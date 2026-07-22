"""auto_fix — automatically repair render diagnostics defects."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated, Any, cast

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.auto_fix import AutoFixPlan, Defect, DefectType
from app.schemas.auto_fix import AutoFixResult, FixItem
from app.tools.render._shared import render_workspace


def _defect_type_from_tag(tag: str) -> DefectType:
    value = tag.strip()
    for defect_type in DefectType:
        if value == defect_type.value or value.startswith(f"{defect_type.value} "):
            return defect_type
    return DefectType.LEVEL_JUMP


def _window_bounds(windows: list[dict[str, Any]], index: int) -> tuple[float, float]:
    window = windows[index]
    start = float(window.get("start_s", window.get("offset_s", 0.0)) or 0.0)
    if "end_s" in window:
        return start, float(window.get("end_s") or start)

    next_offsets = [
        float(next_window["offset_s"])
        for next_window in windows[index + 1 :]
        if "offset_s" in next_window
    ]
    if next_offsets and next_offsets[0] > start:
        return start, next_offsets[0]
    return start, start + 4.0


@tool(
    name="auto_fix",
    tags={"namespace:render:diagnostics", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": False},
    description=(
        "Analyze render diagnostics defects and generate fix commands. "
        "With dry_run=True (default), returns the fix plan without applying. "
        "With dry_run=False, runs ffmpeg fix chain and writes MIX_fixed.mp3."
    ),
    meta={"timeout_s": 600.0},
    timeout=600.0,
    task=True,
)
async def auto_fix(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    mix_path: Annotated[
        str | None,
        Field(description="Custom mix path (default: workspace MIX.mp3)"),
    ] = None,
    dry_run: Annotated[bool, Field(description="Preview fix plan without applying")] = True,
    ctx: Context = CurrentContext(),
) -> AutoFixResult:
    ws = Path(render_workspace(version_id))
    diag_path = ws / "diagnostics.json"
    path = mix_path or str(ws / "MIX.mp3")

    defects: list[Defect] = []
    if diag_path.exists():
        diag_data = json.loads(diag_path.read_text())
        windows = cast(list[dict[str, Any]], diag_data.get("windows", []))
        for i, w in enumerate(windows):
            start_s, end_s = _window_bounds(windows, i)
            for tag in w.get("tags", []):
                defects.append(
                    Defect(
                        defect_type=_defect_type_from_tag(str(tag)),
                        start_s=start_s,
                        end_s=end_s,
                        severity=w.get("severity", 1.0),
                        rms_db=w.get("rms_db", 0),
                        low_db=w.get("low_db", 0),
                    )
                )

    plan = AutoFixPlan(defects=defects, original_path=path)
    plan.generate_fixes()

    result = AutoFixResult(
        dry_run=dry_run,
        defects_found=len(defects),
        fixes=[
            FixItem(type=f.ffmpeg_filter[:40], at_s=f.start_s, action=f.description)
            for f in plan.fixes
        ],
        fixed_path=None,
    )

    if not dry_run and plan.fixes:
        fixed_path = str(ws / "MIX_fixed.mp3")
        cmd = plan.ffmpeg_fix_chain(path, fixed_path)
        subprocess.run(cmd, check=True)
        result = AutoFixResult(
            dry_run=dry_run,
            defects_found=len(defects),
            fixes=result.fixes,
            fixed_path=fixed_path,
        )

    return result
