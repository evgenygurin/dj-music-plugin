"""validate_grid_workflow prompt references only real MCP surface."""

from __future__ import annotations

from app.prompts.validate_grid_workflow import validate_grid_workflow


def _body(res: object) -> str:
    m = res.messages[0]  # type: ignore[attr-defined]
    content = m.content
    return getattr(content, "text", str(content))


def test_validate_grid_prompt_mentions_real_surface() -> None:
    res = validate_grid_workflow(version_id=131)
    text = _body(res)
    assert "render_validate_grid" in text
    assert "local://render/131/" in text
    assert "render_beatgrid" in text
    assert "reference://render/validation" in text


def test_render_prompt_now_includes_validation_step() -> None:
    from app.prompts.render_set_workflow import render_set_workflow

    text = _body(render_set_workflow(version_id=131))
    assert "render_validate_grid" in text
    assert "validate_grid_workflow" in text
