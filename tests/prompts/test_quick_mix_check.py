"""quick_mix_check tests."""

from __future__ import annotations

import pytest
from fastmcp.prompts import Message, PromptResult

from app.prompts.quick_mix_check import quick_mix_check


def _msg_text(m: Message) -> str:
    return m.content.text if hasattr(m.content, "text") else str(m.content)


def test_returns_prompt_result() -> None:
    r = quick_mix_check(from_track_id=1, to_track_id=2)
    assert isinstance(r, PromptResult)
    assert isinstance(r.messages[0], Message)


def test_body_mentions_score_resource() -> None:
    r = quick_mix_check(from_track_id=1, to_track_id=2)
    text = _msg_text(r.messages[0])
    assert "local://transition/1/2/score" in text
    assert "local://transition/1/2/explain" in text


def test_description_mentions_pair() -> None:
    r = quick_mix_check(from_track_id=1, to_track_id=2)
    assert "1" in (r.description or "") and "2" in (r.description or "")


def test_explicit_direction() -> None:
    r = quick_mix_check(from_track_id=99, to_track_id=42)
    text = _msg_text(r.messages[0])
    assert "99/42" in text


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Phase 5 server wiring", strict=False)
async def test_prompt_registered(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    assert any(p.name == "quick_mix_check" for p in prompts)
