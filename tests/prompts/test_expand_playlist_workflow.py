"""expand_playlist_workflow tests."""

from __future__ import annotations

import pytest
from fastmcp.prompts import Message, PromptResult

from app.prompts.expand_playlist_workflow import expand_playlist_workflow


def _msg_text(m: Message) -> str:
    return m.content.text if hasattr(m.content, "text") else str(m.content)


def test_returns_prompt_result() -> None:
    r = expand_playlist_workflow(playlist_id=10, target_count=50)
    assert isinstance(r, PromptResult)
    assert isinstance(r.messages[0], Message)


def test_description_has_target_count() -> None:
    r = expand_playlist_workflow(playlist_id=10, target_count=50)
    assert "50" in (r.description or "")


def test_body_mentions_provider_search() -> None:
    r = expand_playlist_workflow(playlist_id=10, target_count=20)
    text = _msg_text(r.messages[0])
    assert "provider_search" in text or "provider_read" in text
    assert "track_features" in text
    assert "classify_mood" in text or "mood" in text


@pytest.mark.asyncio
async def test_prompt_registered(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    assert any(p.name == "expand_playlist_workflow" for p in prompts)
