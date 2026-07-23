from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan
from app.domain.render.models import (
    BeatgridEntry,
    RenderMode,
    RenderPlan,
    StemSegment,
    TrackInput,
    TrackSegment,
)
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest
from app.domain.render.segments import ClassicSegmentFactory


def _inputs(n: int, *, bpm: float = 130.0) -> list[TrackInput]:
    return [
        TrackInput(
            track_id=i,
            yandex_id=i,
            title=f"t{i}",
            bpm=bpm,
            key_code=1,
            mix_in_ms=0,
            integrated_lufs=-12.0,
            file_path=f"/x{i}.mp3",
            duration_ms=600_000,
        )
        for i in range(n)
    ]


def _grid(n: int) -> dict[int, BeatgridEntry]:
    return {
        i: BeatgridEntry(
            track_id=i,
            trim_start_s=0.0,
            refined_trim_s=0.0,
            gain_db=0.0,
            phase_ms=0.0,
        )
        for i in range(n)
    }


def _req(*, version_id: int = 1, stem: bool = False, **kw: object) -> RenderRequest:
    base = {
        "version_id": version_id,
        "workspace": "/tmp/ws",
        "timestamp": "20260101-000000",
    }
    base.update(kw)
    return RenderRequest(stem=stem, **base)


def test_assemble_classic_returns_plan_with_classic_mode() -> None:
    settings = RenderSettings()
    request = _req(stem=False)
    inputs = _inputs(2)
    bar_plan = BarPlan(transition_bars=(16,), body_bars=[24, 24])

    plan = RenderPlanner().assemble(settings, request, inputs, _grid(2), bar_plan, stem_paths=None)

    assert isinstance(plan, RenderPlan)
    assert plan.mode is RenderMode.CLASSIC
    assert all(isinstance(seg, TrackSegment) for seg in plan.segments)
    assert plan.stem_segments is None
    assert plan.n == 2


def test_assemble_stem_returns_plan_with_stem_mode() -> None:
    settings = RenderSettings()
    request = _req(stem=True)
    inputs = _inputs(2)
    stem_paths = {i: {stem: f"/stems/{i}/{stem}.flac" for stem in STEM_NAMES} for i in range(2)}
    bar_plan = BarPlan(transition_bars=(16,), body_bars=[24, 24])

    plan = RenderPlanner().assemble(settings, request, inputs, _grid(2), bar_plan, stem_paths)

    assert plan.mode is RenderMode.STEM
    assert plan.segments == []
    assert plan.stem_segments is not None
    assert all(isinstance(seg, StemSegment) for seg in plan.stem_segments)
    assert plan.n == 2


def test_assemble_carries_effects_from_request() -> None:
    settings = RenderSettings()
    request = _req(stem=False, echo="techno_standard", reverb="techno_hall")
    bar_plan = BarPlan(transition_bars=(), body_bars=[24])

    plan = RenderPlanner().assemble(
        settings,
        request,
        _inputs(1),
        _grid(1),
        bar_plan,
        stem_paths=None,
    )

    assert plan.echo_preset == "techno_standard"
    assert plan.reverb_preset == "techno_hall"


def test_classic_factory_ignores_stem_paths() -> None:
    factory = ClassicSegmentFactory()

    segments = factory.build_segments(
        geometries=[],
        inputs=_inputs(1),
        stem_paths={0: {"drums": "/x.wav"}},
        settings=RenderSettings(),
        request=_req(stem=False),
    )

    assert segments == []


STEM_NAMES = ("drums", "bass", "harmonic", "instrumental", "acappella")
