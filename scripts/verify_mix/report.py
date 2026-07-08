"""Aggregate check results into a report — text + JSON + exit code."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .checks import CheckResult, Status


@dataclass(frozen=True, slots=True)
class Report:
    target: str
    results: tuple[CheckResult, ...]

    @property
    def counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in Status}
        for result in self.results:
            counts[result.status.value] += 1
        return counts

    @property
    def exit_code(self) -> int:
        """Non-zero on any FAIL — delivery gates on this."""
        return 1 if any(r.status is Status.FAIL for r in self.results) else 0

    def to_text(self) -> str:
        lines = [f"mix-verify: {self.target}"]
        width = max((len(r.name) for r in self.results), default=0)
        for r in self.results:
            lines.append(f"  [{r.status.value:<4}] {r.name:<{width}}  {r.message}")
        c = self.counts
        lines.append(
            f"{c['PASS']} PASS, {c['WARN']} WARN, {c['FAIL']} FAIL -> exit {self.exit_code}"
        )
        return "\n".join(lines)

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "target": self.target,
            "counts": self.counts,
            "exit_code": self.exit_code,
            "results": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


def build_report(target: str, results: list[CheckResult]) -> Report:
    return Report(target=target, results=tuple(results))
