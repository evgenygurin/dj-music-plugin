"""build_set_workflow prompt tests."""

from __future__ import annotations

import pytest
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts.build_set_workflow import build_set_workflow


def _msg_text(m: Message) -> str:
    return m.content.text if hasattr(m.content, "text") else str(m.content)


def test_returns_prompt_result() -> None:
    result = build_set_workflow(playlist_id=42)
    assert isinstance(result, PromptResult)
    assert isinstance(result.messages[0], Message)


def test_description_includes_playlist_id() -> None:
    result = build_set_workflow(playlist_id=42, template="classic_60")
    assert "42" in (result.description or "")
    assert "classic_60" in (result.description or "")


def test_body_mentions_all_steps() -> None:
    result = build_set_workflow(playlist_id=42)
    text = _msg_text(result.messages[0])
    assert "entity_list" in text
    assert "entity_create" in text
    assert "transition_score_pool" in text
    assert "sequence_optimize" in text


def test_default_template_used() -> None:
    result = build_set_workflow(playlist_id=1)
    text = _msg_text(result.messages[0])
    assert "classic_60" in text


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Phase 5 server wiring", strict=False)
async def test_prompt_registered(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    assert any(p.name == "build_set_workflow" for p in prompts)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Phase 5 server wiring", strict=False)
async def test_prompt_invocable_via_client(client: object) -> None:
    rendered = await client.get_prompt(  # type: ignore[attr-defined]
        "build_set_workflow", arguments={"playlist_id": 10, "template": "peak_hour_60"}
    )
    assert any("10" in getattr(m.content, "text", str(m.content)) for m in rendered.messages)
