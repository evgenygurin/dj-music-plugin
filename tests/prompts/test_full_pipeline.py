"""full_pipeline prompt tests."""

from __future__ import annotations

import pytest
from fastmcp.prompts import Message, PromptResult

from app.prompts.full_pipeline import full_pipeline


def _msg_text(m: Message) -> str:
    return m.content.text if hasattr(m.content, "text") else str(m.content)


def test_returns_prompt_result() -> None:
    r = full_pipeline(playlist_id=10, template="classic_60")
    assert isinstance(r, PromptResult)


def test_body_chains_three_workflows() -> None:
    r = full_pipeline(playlist_id=10, template="classic_60")
    text = _msg_text(r.messages[0])
    assert "expand_playlist_workflow" in text
    assert "build_set_workflow" in text
    assert "deliver_set_workflow" in text


def test_description_mentions_pipeline() -> None:
    r = full_pipeline(playlist_id=10)
    assert "pipeline" in (r.description or "").lower()


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Phase 5 server wiring", strict=False)
async def test_prompt_registered(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    assert any(p.name == "full_pipeline" for p in prompts)
