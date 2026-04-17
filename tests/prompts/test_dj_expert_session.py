"""dj_expert_session prompt tests."""

from __future__ import annotations

import pytest
from fastmcp.prompts import Message, PromptResult

from app.prompts.dj_expert_session import dj_expert_session


def test_returns_prompt_result_directly() -> None:
    result = dj_expert_session()
    assert isinstance(result, PromptResult)
    assert result.description is not None
    assert len(result.messages) >= 1
    assert isinstance(result.messages[0], Message)


def test_description_mentions_dj() -> None:
    result = dj_expert_session()
    assert "DJ" in (result.description or "")


def _msg_text(m: Message) -> str:
    return m.content.text if hasattr(m.content, "text") else str(m.content)


def test_content_mentions_camelot_and_subgenres() -> None:
    result = dj_expert_session()
    text = " ".join(_msg_text(m) for m in result.messages)
    assert "camelot" in text.lower() or "Camelot" in text
    assert "subgenre" in text.lower()


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Phase 5 server wiring: build_mcp_app_for_tests not yet implemented",
    strict=False,
)
async def test_prompt_reachable_via_client(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    assert any(p.name == "dj_expert_session" for p in prompts)
    rendered = await client.get_prompt("dj_expert_session", arguments={})  # type: ignore[attr-defined]
    assert len(rendered.messages) >= 1
