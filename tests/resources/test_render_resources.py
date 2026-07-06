# tests/resources/test_render_resources.py
import json

import pytest

from app.resources.render import render_defaults_resource, render_job_status_resource


@pytest.mark.asyncio
async def test_defaults_resource_has_settings():
    payload = json.loads(await render_defaults_resource())
    assert payload["target_bpm"] == 130.0
    assert payload["transition_bars"] == 32


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
