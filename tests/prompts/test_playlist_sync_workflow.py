"""playlist_sync_workflow prompt tests."""

from __future__ import annotations

import pytest
from fastmcp.prompts import Message, PromptResult

from app.prompts.playlist_sync_workflow import playlist_sync_workflow


def _msg_text(m: Message) -> str:
    return m.content.text if hasattr(m.content, "text") else str(m.content)


def test_returns_prompt_result() -> None:
    result = playlist_sync_workflow(playlist_id=10, direction="diff")
    assert isinstance(result, PromptResult)
    assert isinstance(result.messages[0], Message)


def test_description_includes_normalized_direction() -> None:
    result = playlist_sync_workflow(playlist_id=10, direction=" PUSH ")
    assert "10" in (result.description or "")
    assert "direction=push" in (result.description or "")


def test_body_mentions_preview_conflict_gate_and_convergence() -> None:
    result = playlist_sync_workflow(playlist_id=10, direction="pull")
    text = _msg_text(result.messages[0])
    assert 'playlist_sync(playlist_id=10, direction="diff"' in text
    assert "dry_run=true" in text
    assert "provider_read" in text
    assert "pause and confirm" in text
    assert "converged" in text


def test_rejects_unknown_direction() -> None:
    with pytest.raises(ValueError, match="direction must be one of"):
        playlist_sync_workflow(playlist_id=10, direction="merge")


@pytest.mark.asyncio
async def test_prompt_registered(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    assert any(p.name == "playlist_sync_workflow" for p in prompts)


@pytest.mark.asyncio
async def test_prompt_invocable_via_client(client: object) -> None:
    rendered = await client.get_prompt(  # type: ignore[attr-defined]
        "playlist_sync_workflow", arguments={"playlist_id": 10, "direction": "pull"}
    )
    assert any(
        "direction='pull'" in getattr(m.content, "text", str(m.content)) for m in rendered.messages
    )
