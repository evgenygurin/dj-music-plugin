from __future__ import annotations

import json

from scripts.verify_mix.checks import CheckResult, Status
from scripts.verify_mix.report import build_report


def _results() -> list[CheckResult]:
    return [
        CheckResult("honest_duration", Status.PASS, "ok"),
        CheckResult("vocal_masking", Status.WARN, "borderline"),
        CheckResult("clipping", Status.FAIL, "0.0 dBFS", {"max_volume_db": 0.0}),
    ]


def test_counts() -> None:
    report = build_report("mix.mp3", _results())

    assert report.counts == {"PASS": 1, "WARN": 1, "FAIL": 1}


def test_exit_code_nonzero_on_fail() -> None:
    assert build_report("mix.mp3", _results()).exit_code == 1


def test_exit_code_zero_without_fail() -> None:
    results = [CheckResult("clipping", Status.PASS, "ok")]

    assert build_report("mix.mp3", results).exit_code == 0


def test_text_lists_every_check() -> None:
    text = build_report("mix.mp3", _results()).to_text()

    assert "honest_duration" in text
    assert "[FAIL]" in text
    assert "exit 1" in text


def test_json_roundtrip() -> None:
    report = build_report("mix.mp3", _results())

    payload = json.loads(report.to_json())

    assert payload["exit_code"] == 1
    assert payload["counts"]["FAIL"] == 1
    assert len(payload["results"]) == 3
    assert payload["results"][2]["detail"]["max_volume_db"] == 0.0
