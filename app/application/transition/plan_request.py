"""Application service for planning from persisted analysis contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.application.analysis.persistence import snapshot_from_record
from app.domain.analysis import AnalysisSnapshot
from app.domain.mixing.alignment import AlignmentRequest
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.selection import SelectionPolicy


class AnalysisSnapshotStore(Protocol):
    async def get_analysis_snapshot(self, identity_hash: str) -> dict[str, Any] | None: ...


class FeatureCatalog(Protocol):
    async def features(self, track_ids: list[int]) -> dict[int, Any]: ...


class CandidateGeneratorPort(Protocol):
    def generate(
        self, source: AnalysisSnapshot, target: AnalysisSnapshot, request: AlignmentRequest
    ) -> tuple[CandidateTransition, ...]: ...


class PlanTransitionPort(Protocol):
    async def execute_async(self, candidates: Any, features: Any, policy: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class PlanTransitionRequest:
    source_track_id: int
    target_track_id: int
    source_analysis_identity: str
    target_analysis_identity: str
    bars: int
    policy: SelectionPolicy

    def __post_init__(self) -> None:
        if self.source_track_id < 1 or self.target_track_id < 1:
            raise ValueError("track IDs must be positive")
        if self.source_track_id == self.target_track_id:
            raise ValueError("source and target tracks must differ")
        if not self.source_analysis_identity.strip() or not self.target_analysis_identity.strip():
            raise ValueError("analysis identities must not be empty")
        if self.bars <= 0:
            raise ValueError("bars must be positive")


class PlanTransitionService:
    """Resolve real persisted analysis, generate candidates, then route planning."""

    def __init__(
        self,
        analysis_store: AnalysisSnapshotStore,
        feature_catalog: FeatureCatalog,
        candidate_generator: CandidateGeneratorPort,
        planner: PlanTransitionPort,
    ) -> None:
        self._analysis_store = analysis_store
        self._feature_catalog = feature_catalog
        self._candidate_generator = candidate_generator
        self._planner = planner

    async def execute(self, request: PlanTransitionRequest) -> Any:
        source = await self._load_snapshot(request.source_analysis_identity)
        target = await self._load_snapshot(request.target_analysis_identity)
        features = await self._feature_catalog.features(
            [request.source_track_id, request.target_track_id]
        )
        source_features = features.get(request.source_track_id)
        target_features = features.get(request.target_track_id)
        if source_features is None or target_features is None:
            raise ValueError("track features not found")

        candidates = self._candidate_generator.generate(
            source, target, AlignmentRequest(request.bars)
        )
        if not candidates:
            raise ValueError("no transition candidates generated from persisted analysis")
        return await self._planner.execute_async(
            candidates,
            (source_features, target_features),
            request.policy,
        )

    async def _load_snapshot(self, identity: str) -> AnalysisSnapshot:
        record = await self._analysis_store.get_analysis_snapshot(identity)
        if record is None:
            raise ValueError(f"analysis snapshot not found: {identity}")
        snapshot = snapshot_from_record(record)
        if snapshot.identity_hash != identity:
            raise ValueError(f"analysis snapshot identity mismatch: {identity}")
        return snapshot
