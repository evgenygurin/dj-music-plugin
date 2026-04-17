"""deliver_set_workflow tests."""

from __future__ import annotations

import pytest
from fastmcp.prompts import Message, PromptResult

from app.prompts.deliver_set_workflow import deliver_set_workflow


def _msg_text(m: Message) -> str:
    return m.content.text if hasattr(m.content, "text") else str(m.content)


def test_returns_prompt_result() -> None:
    result = deliver_set_workflow(set_id=100)
    assert isinstance(result, PromptResult)
    assert isinstance(result.messages[0], Message)


def test_description_has_set_id() -> None:
    result = deliver_set_workflow(set_id=100)
    assert "100" in (result.description or "")


def test_body_mentions_conflict_gate() -> None:
    result = deliver_set_workflow(set_id=100)
    text = _msg_text(result.messages[0])
    assert "conflict" in text.lower() or "elicit" in text.lower()


def test_body_mentions_export_formats() -> None:
    result = deliver_set_workflow(set_id=100)
    text = _msg_text(result.messages[0])
    for fmt in ("m3u8", "rekordbox", "cheatsheet"):
        assert fmt in text.lower()


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Phase 5 server wiring", strict=False)
async def test_prompt_registered(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    assert any(p.name == "deliver_set_workflow" for p in prompts)
