from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rimjoba_prompt.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_list_modes() -> None:
    proc = _run("--list")
    assert proc.returncode == 0
    assert "street_trap" in proc.stdout
    assert "late_night" in proc.stdout


def test_cli_assemble_street_trap() -> None:
    proc = _run("street_trap")
    assert proc.returncode == 0
    assert "STYLE:" in proc.stdout
    assert "NEGATIVE:" in proc.stdout
    assert "deadpan delivery" in proc.stdout
    assert "Russian trap" in proc.stdout


def test_cli_unknown_mode_exits_2() -> None:
    proc = _run("not_a_mode")
    assert proc.returncode == 2
    assert "unknown" in proc.stderr.lower() or "unknown" in proc.stdout.lower()
