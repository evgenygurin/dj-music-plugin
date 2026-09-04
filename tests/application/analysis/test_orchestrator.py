from dataclasses import dataclass, field

from app.application.analysis.orchestrator import AnalysisOrchestrator
from app.application.analysis.tiers import AnalysisTier
from app.domain.analysis.snapshot import AnalysisSnapshot


@dataclass
class FakeGateway:
    calls: list[AnalysisTier] = field(default_factory=list)

    def run(
        self, track_id: int, tier: AnalysisTier, config: dict[str, object]
    ) -> dict[str, object]:
        self.calls.append(tier)
        return {"source_hash": f"track-{track_id}", "schema_version": "1"}


def test_basic_never_requests_deep_analysis() -> None:
    gateway = FakeGateway()
    snapshot = AnalysisOrchestrator(gateway).analyze(7, AnalysisTier.BASIC, {})
    assert isinstance(snapshot, AnalysisSnapshot)
    assert gateway.calls == [AnalysisTier.BASIC]


def test_mix_ready_requests_only_mix_ready_tier() -> None:
    gateway = FakeGateway()
    AnalysisOrchestrator(gateway).analyze(7, AnalysisTier.MIX_READY, {})
    assert gateway.calls == [AnalysisTier.MIX_READY]


def test_deep_requires_explicit_deep_tier() -> None:
    gateway = FakeGateway()
    AnalysisOrchestrator(gateway).analyze(7, AnalysisTier.DEEP, {})
    assert gateway.calls == [AnalysisTier.DEEP]
