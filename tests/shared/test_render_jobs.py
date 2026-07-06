from app.shared.render_jobs import RENDER_JOBS, RenderJob


def test_register_update_read():
    RENDER_JOBS.clear()
    job = RENDER_JOBS.start(job_id="v131-abc", version_id=131, phase="beatgrid")
    assert isinstance(job, RenderJob)
    RENDER_JOBS.update("v131-abc", phase="mixdown", progress=3, total=15, message="track 3")
    got = RENDER_JOBS.get("v131-abc")
    assert got.phase == "mixdown"
    assert got.progress == 3 and got.total == 15
    assert got.message == "track 3"


def test_get_unknown_returns_none():
    RENDER_JOBS.clear()
    assert RENDER_JOBS.get("nope") is None
