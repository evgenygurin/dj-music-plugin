from __future__ import annotations

import json

import pytest

from app.schemas.render import GridCheckResult, TrackGridCheck
from app.shared.json_utils import pydantic_json_dumps, to_jsonable


def test_pydantic_json_dumps_handles_grid_check_result() -> None:
    model = GridCheckResult(
        version_id=248,
        job_id="v248",
        mix_path="generated-sets/render/v248/MIX.mp3",
        target_bpm=130.0,
        tracks=[TrackGridCheck(track_id=3216, title="Test", bpm_measured=130.0, status="ok")],
        summary="ok",
    )
    # This was the failing call: json.dumps(model) -> TypeError
    dumped = pydantic_json_dumps(model, indent=2)
    parsed = json.loads(dumped)
    assert parsed["version_id"] == 248
    assert parsed["tracks"][0]["track_id"] == 3216

    # to_jsonable also works
    assert to_jsonable(model)["version_id"] == 248

    # Direct model_dump also works (documented alternative)
    assert json.dumps(model.model_dump(), indent=2)
    assert json.dumps(model.model_dump(mode="json"), indent=2)


def test_json_dumps_direct_model_fails_without_helper() -> None:
    model = GridCheckResult(version_id=1, job_id="j", mix_path="p", target_bpm=120.0)
    try:
        json.dumps(model)
        pytest.fail("should have raised TypeError")
    except TypeError as e:
        assert "not JSON serializable" in str(e)
