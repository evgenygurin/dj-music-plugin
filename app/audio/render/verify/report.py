"""Aggregate verification check results into a structured report."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.audio.render.verify.checks import CheckResult, Status


@dataclass(frozen=True, slots=True)
class VerifyReport:
    results: tuple[CheckResult, ...] = field(default_factory=tuple)

    @property
    def counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in Status}
        for r in self.results:
            counts[r.status.value] += 1
        return counts

    @property
    def exit_code(self) -> int:
        return 1 if any(r.status is Status.FAIL for r in self.results) else 0

    def to_text(self) -> str:
        lines = ["render-verify"]
        width = max((len(r.name) for r in self.results), default=0)
        for r in self.results:
            lines.append(f"  [{r.status.value:<4}] {r.name:<{width}}  {r.message}")
        c = self.counts
        lines.append(
            f"{c['PASS']} PASS, {c['WARN']} WARN, {c['FAIL']} FAIL → exit {self.exit_code}"
        )
        return "\n".join(lines)

    def to_json(self) -> str:
        payload: dict[str, Any] = {
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
