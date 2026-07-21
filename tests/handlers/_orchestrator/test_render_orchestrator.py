from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.domain.render.models import RenderMode, TrackInput
from app.domain.render.request import RenderRequest
from app.handlers._orchestrator.render_orchestrator import RenderOrchestrator
from app.schemas.render import RenderMixdownResult
from app.shared.render_jobs import RENDER_JOBS


@dataclass
class _Recorder:
    calls: list[str]


class _StubUow:
    def __init__(self, inputs: list[TrackInput], recorder: _Recorder) -> None:
        self.session = None

        class _SV:
            async def get_render_inputs(self, _version_id: int) -> list[TrackInput]:
                recorder.calls.append("inputs")
                return inputs

        self.set_versions = _SV()


class _PresetApplier:
    def __init__(self, recorder: _Recorder) -> None:
        self._recorder = recorder

    async def apply(self, settings: Any, ctx: Any, subgenre: str | None) -> None:
        assert settings is not None
        assert ctx is None
        assert subgenre == "dub_techno"
        self._recorder.calls.append("preset")


class _BeatgridProvider:
    def __init__(self, recorder: _Recorder) -> None:
        self._recorder = recorder

    async def ensure(self, ctx: Any, request: RenderRequest, uow: Any) -> None:
        assert ctx is None
        assert request.version_id == 1
        assert uow is not None
        self._recorder.calls.append("ensure")

    def load(self, workspace: str) -> dict[int, Any]:
        assert workspace == "/tmp/ws"
        self._recorder.calls.append("load")
        return {}


class _StemResolver:
    def __init__(self, recorder: _Recorder, result: dict[int, dict[str, str]] | None = None) -> None:
        self._recorder = recorder
        self._result = result

    async def resolve(
        self,
        ctx: Any,
        uow: Any,
        inputs: list[TrackInput],
    ) -> dict[int, dict[str, str]] | None:
        assert ctx is None
        assert uow is not None
        assert inputs
        self._recorder.calls.append("resolve")
        return self._result


class _Planner:
    def __init__(self, recorder: _Recorder, expected_stems: dict[int, dict[str, str]] | None) -> None:
        self._recorder = recorder
        self._expected_stems = expected_stems

    def assemble(
        self,
        settings: Any,
        request: RenderRequest,
        inputs: list[TrackInput],
        grid: dict[int, Any],
        bar_plan: Any,
        stem_paths: dict[int, dict[str, str]] | None,
    ) -> Any:
        assert settings is not None
        assert request.version_id == 1
        assert inputs
        assert grid == {}
        assert len(bar_plan.body_bars) == len(inputs)
        assert stem_paths == self._expected_stems
        self._recorder.calls.append("assemble")
        return type("Plan", (), {"mode": request.mode, "n": len(inputs)})()


class _Executor:
    def __init__(self, recorder: _Recorder, expected_mode: RenderMode) -> None:
        self._recorder = recorder
        self._expected_mode = expected_mode

    async def execute(self, ctx: Any, request: RenderRequest, plan: Any) -> RenderMixdownResult:
        assert ctx is None
        assert request.version_id == 1
        assert plan.mode is self._expected_mode
        self._recorder.calls.append("execute")
        return RenderMixdownResult(job_id="x", version_id=1, out_path="/o", duration_s=0.0)


def _req(*, stem: bool = False) -> RenderRequest:
    return RenderRequest(
        version_id=1,
        workspace="/tmp/ws",
        timestamp="20260101",
        stem=stem,
        subgenre="dub_techno",
    )


def _inputs(n: int) -> list[TrackInput]:
    return [
        TrackInput(
            track_id=i,
            yandex_id=i,
            title=f"t{i}",
            bpm=130.0,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path=f"/x{i}.mp3",
        )
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_run_invokes_preset_applier_before_beatgrid_provider() -> None:
    RENDER_JOBS.clear()
    recorder = _Recorder(calls=[])
    orchestrator = RenderOrchestrator(
        _StubUow(_inputs(1), recorder),
        preset_applier=_PresetApplier(recorder),
        beatgrid_provider=_BeatgridProvider(recorder),
        stem_resolver=_StemResolver(recorder),
        planner=_Planner(recorder, expected_stems=None),
        executor=_Executor(recorder, expected_mode=RenderMode.CLASSIC),
    )

    await orchestrator.run(ctx=None, request=_req(stem=False))

    assert recorder.calls[:2] == ["preset", "ensure"]


@pytest.mark.asyncio
async def test_run_skips_stem_resolver_in_classic_mode() -> None:
    RENDER_JOBS.clear()
    recorder = _Recorder(calls=[])
    orchestrator = RenderOrchestrator(
        _StubUow(_inputs(2), recorder),
        preset_applier=_PresetApplier(recorder),
        beatgrid_provider=_BeatgridProvider(recorder),
        stem_resolver=_StemResolver(recorder),
        planner=_Planner(recorder, expected_stems=None),
        executor=_Executor(recorder, expected_mode=RenderMode.CLASSIC),
    )

    await orchestrator.run(ctx=None, request=_req(stem=False))

    assert recorder.calls == ["preset", "ensure", "inputs", "load", "assemble", "execute"]


@pytest.mark.asyncio
async def test_run_calls_stem_resolver_before_planner_in_stem_mode() -> None:
    RENDER_JOBS.clear()
    recorder = _Recorder(calls=[])
    stem_paths = {0: {"drums": "/stems/0-drums.m4a"}}
    orchestrator = RenderOrchestrator(
        _StubUow(_inputs(1), recorder),
        preset_applier=_PresetApplier(recorder),
        beatgrid_provider=_BeatgridProvider(recorder),
        stem_resolver=_StemResolver(recorder, result=stem_paths),
        planner=_Planner(recorder, expected_stems=stem_paths),
        executor=_Executor(recorder, expected_mode=RenderMode.STEM),
    )

    await orchestrator.run(ctx=None, request=_req(stem=True))

    assert recorder.calls == ["preset", "ensure", "inputs", "load", "resolve", "assemble", "execute"]
