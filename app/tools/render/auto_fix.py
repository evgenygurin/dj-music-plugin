"""auto_fix — automatically repair render diagnostics defects."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.auto_fix import AutoFixPlan, Defect, DefectType
from app.schemas.auto_fix import AutoFixResult, FixItem
from app.tools.render._shared import render_workspace


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
    dry_run: Annotated[
        bool, Field(description="Preview fix plan without applying")
    ] = True,
    ctx: Context = CurrentContext(),
) -> AutoFixResult:
    ws = Path(render_workspace(version_id))
    diag_path = ws / "diagnostics.json"
    path = mix_path or str(ws / "MIX.mp3")

    defects: list[Defect] = []
    if diag_path.exists():
        diag_data = json.loads(diag_path.read_text())
        for w in diag_data.get("windows", []):
            for tag in w.get("tags", []):
                try:
                    dt = DefectType(tag)
                except ValueError:
                    dt = DefectType.LEVEL_JUMP
                defects.append(Defect(
                    defect_type=dt,
                    start_s=w.get("start_s", 0),
                    end_s=w.get("end_s", 0),
                    severity=w.get("severity", 1.0),
                    rms_db=w.get("rms_db", 0),
                    low_db=w.get("low_db", 0),
                ))

    plan = AutoFixPlan(defects=defects, original_path=path)
    plan.generate_fixes()

    result = AutoFixResult(
        dry_run=dry_run,
        defects_found=len(defects),
        fixes=[
            FixItem(type=f.ffmpeg_filter[:40], at_s=f.start_s, action=f.description)
            for f in plan.fixes
        ],
    )

    if not dry_run and plan.fixes:
        import subprocess

        fixed_path = str(ws / "MIX_fixed.mp3")
        cmd = plan.ffmpeg_fix_chain(path, fixed_path)
        subprocess.run(cmd, shell=True, check=True)
        result.fixed_path = fixed_path

    return result
