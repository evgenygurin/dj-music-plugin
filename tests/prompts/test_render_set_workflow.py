"""render_set_workflow prompt references only real MCP surface."""

from __future__ import annotations

from app.prompts.render_set_workflow import render_set_workflow


def _body(res: object) -> str:
    m = res.messages[0]  # type: ignore[attr-defined]
    content = m.content
    return getattr(content, "text", str(content))


def test_render_prompt_mentions_real_surface() -> None:
    res = render_set_workflow(version_id=131)
    text = _body(res)
    # references real tools/resources only
    assert "render_beatgrid" in text
    assert "render_mixdown" in text
    assert 'entity="audio_file"' in text
    assert "local://render/" in text
    assert "deliver_set_workflow" in text
