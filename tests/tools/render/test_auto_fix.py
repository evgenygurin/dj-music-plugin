from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.tools.render import auto_fix as mod


@pytest.mark.asyncio
async def test_auto_fix_parses_real_diagnostics_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "diagnostics.json").write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "offset_s": 4.0,
                        "rms_db": -8.0,
                        "low_db": -32.0,
                        "tags": ["LEVEL-JUMP +8dB", "DROPOUT -30dB", "bass-thin"],
                    },
                    {"offset_s": 8.0, "rms_db": -9.0, "low_db": -20.0, "tags": []},
                ]
            }
        )
    )
    monkeypatch.setattr(mod, "render_workspace", lambda version_id: str(tmp_path))

    result = await mod.auto_fix(version_id=1, dry_run=True, ctx=None)  # type: ignore[arg-type]

    assert result.defects_found == 3
    assert len(result.fixes) == 3
    assert {fix.at_s for fix in result.fixes} == {4.0}
    assert any("Level jump fix" in fix.action for fix in result.fixes)
    assert any("dropout" in fix.action for fix in result.fixes)
    assert any("Bass boost" in fix.action for fix in result.fixes)


@pytest.mark.asyncio
async def test_auto_fix_runs_ffmpeg_without_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mix_path = "mix'; touch /tmp/pwn #.mp3"
    (tmp_path / "diagnostics.json").write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "start_s": 1.0,
                        "end_s": 2.0,
                        "rms_db": -30.0,
                        "low_db": -30.0,
                        "tags": ["DROPOUT"],
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(mod, "render_workspace", lambda version_id: str(tmp_path))
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(cmd: object, **kwargs: object) -> subprocess.CompletedProcess[object]:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = await mod.auto_fix(
        version_id=1,
        mix_path=mix_path,
        dry_run=False,
        ctx=None,  # type: ignore[arg-type]
    )

    assert result.fixed_path == str(tmp_path / "MIX_fixed.mp3")
    assert len(calls) == 1
    cmd, kwargs = calls[0]
    assert isinstance(cmd, list)
    assert cmd[:3] == ["ffmpeg", "-i", mix_path]
    assert kwargs == {"check": True}
