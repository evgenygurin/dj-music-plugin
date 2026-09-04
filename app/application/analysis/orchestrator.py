"""Tiered application orchestration around existing audio analyzers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, MutableMapping
from typing import Any, Protocol

from app.domain.analysis import AnalysisSnapshot

from .normalizers import beatgrid, cues, phrases, sections, tempo_hypotheses
from .tiers import AnalysisTier, ResourceBudget


class AnalysisGateway(Protocol):
    """Infrastructure adapter that owns concrete analyzer execution."""

    def run(
        self, track_id: int, tier: AnalysisTier, config: dict[str, object]
    ) -> Mapping[str, Any]: ...


class AnalysisOrchestrator:
    """Select exactly one requested analysis tier and normalize its result."""

    def __init__(
        self,
        gateway: AnalysisGateway,
        cache: MutableMapping[str, AnalysisSnapshot] | None = None,
        budget: ResourceBudget | None = None,
    ) -> None:
        self._gateway = gateway
        self._cache = cache
        self._budget = budget or ResourceBudget()

    def analyze(
        self, track_id: int, tier: AnalysisTier, config: dict[str, object]
    ) -> AnalysisSnapshot:
        if not self._budget.allows_analysis(1):
            raise RuntimeError("analysis resource budget exhausted")
        request_key = self._request_key(track_id, tier, config)
        if self._cache is not None and request_key in self._cache:
            return self._cache[request_key]
        raw = self._gateway.run(track_id, tier, config)
        snapshot = self._normalize(raw)
        if self._cache is not None:
            self._cache[request_key] = snapshot
        return snapshot

    @staticmethod
    def _request_key(track_id: int, tier: AnalysisTier, config: Mapping[str, object]) -> str:
        payload = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(f"{track_id}:{tier.name}:{payload}".encode()).hexdigest()

    @staticmethod
    def _normalize(raw: Mapping[str, Any]) -> AnalysisSnapshot:
        return AnalysisSnapshot(
            source_hash=str(raw["source_hash"]),
            schema_version=str(raw.get("schema_version", "1")),
            analyzer_versions=raw.get("analyzer_versions", {}),
            engine_version=str(raw.get("engine_version", "universal-1")),
            model_versions=raw.get("model_versions", {}),
            dsp_backend=str(raw.get("dsp_backend", "unknown")),
            analysis_config_hash=str(raw.get("analysis_config_hash", "")),
            tempo_hypotheses=tempo_hypotheses(raw.get("tempo_hypotheses", ())),
            beatgrid=beatgrid(raw["beatgrid"]) if raw.get("beatgrid") else None,
            phrases=phrases(raw.get("phrases", ())),
            sections=sections(raw.get("sections", ())),
            cues=cues(raw.get("cues", ())),
        )
