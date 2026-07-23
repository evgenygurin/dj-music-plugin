from dataclasses import FrozenInstanceError
from typing import TypedDict

import pytest

from app.config import get_settings
from app.domain.render.models import RenderMode
from app.domain.render.request import RenderRequest


class _BaseRequestKwargs(TypedDict):
    version_id: int
    workspace: str
    timestamp: str


def _base() -> _BaseRequestKwargs:
    return dict(version_id=1, workspace="/tmp/ws", timestamp="20260101-000000")


def _assign_version_id(req: RenderRequest, value: int) -> None:
    req.version_id = value  # type: ignore[misc]


def test_mode_classic_when_stem_false() -> None:
    req = RenderRequest(stem=False, **_base())
    assert req.mode is RenderMode.CLASSIC


def test_mode_stem_when_stem_true() -> None:
    req = RenderRequest(stem=True, **_base())
    assert req.mode is RenderMode.STEM


def test_out_filename_default_uses_settings() -> None:
    req = RenderRequest(**_base())
    assert req.out_filename == get_settings().render.mix_filename


def test_out_filename_explicit_out_name_wins() -> None:
    req = RenderRequest(out_name="custom.mp3", **_base())
    assert req.out_filename == "custom.mp3"


def test_render_request_is_frozen() -> None:
    req = RenderRequest(**_base())
    with pytest.raises(FrozenInstanceError):
        _assign_version_id(req, 2)
