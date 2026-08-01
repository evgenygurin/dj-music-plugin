# tests/resources/test_render_resources.py
import json

import pytest

from app.resources.render import (
    render_defaults_resource,
    render_job_diagnostics_resource,
    render_job_status_resource,
)


@pytest.mark.asyncio
async def test_defaults_resource_has_settings():
    payload = json.loads(await render_defaults_resource())
    assert payload["target_bpm"] == 130.0
    assert payload["transition_bars"] == 48


@pytest.mark.asyncio
async def test_status_resource_unknown_job():
    from app.shared.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await render_job_status_resource("does-not-exist")


@pytest.mark.asyncio
async def test_status_resource_reads_registry():
    from app.shared.render_jobs import RENDER_JOBS

    RENDER_JOBS.clear()
    RENDER_JOBS.start(job_id="v1-x", version_id=1, phase="mixdown")
    RENDER_JOBS.update("v1-x", progress=2, total=5, message="track 2")
    payload = json.loads(await render_job_status_resource("v1-x"))
    assert payload["phase"] == "mixdown" and payload["progress"] == 2


@pytest.mark.asyncio
async def test_diagnostics_resource_malformed_job_id():
    from app.shared.errors import NotFoundError

    # A job_id whose version segment is not an int must raise the typed
    # NotFoundError, not a bare ValueError (→ masked "internal error").
    with pytest.raises(NotFoundError):
        await render_job_diagnostics_resource("not-a-version")


@pytest.mark.asyncio
async def test_grid_check_resource_missing_raises():
    from app.resources.render import render_grid_check_resource
    from app.shared.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await render_grid_check_resource(99999)


@pytest.mark.asyncio
async def test_plan_resource_missing_raises():
    from app.resources.render import render_plan_resource
    from app.shared.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await render_plan_resource(99999)


@pytest.mark.asyncio
async def test_validation_gates_reference():
    from app.resources.render import render_validation_gates_resource

    payload = json.loads(await render_validation_gates_resource())
    assert payload["thresholds_bpm"]["ok"] == 0.5
    assert payload["tool"] == "render_validate_grid"
