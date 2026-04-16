"""Tests for dj_expert_session prompt structure."""

from __future__ import annotations

import pytest
from fastmcp.prompts import PromptResult


@pytest.mark.asyncio
async def test_prompt_returns_two_messages():
    """dj_expert_session returns a PromptResult with user + assistant message pair."""
    from app.controllers.prompts.workflows.dj_expert_session import dj_expert_session

    result = dj_expert_session()
    assert isinstance(result, PromptResult)
    assert len(result.messages) == 2
    assert result.messages[0].role == "user"
    assert result.messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_prompt_references_all_knowledge_resources():
    """User message instructs reading all 4 knowledge:// and library://snapshot."""
    from app.controllers.prompts.workflows.dj_expert_session import dj_expert_session

    result = dj_expert_session()
    user_content = result.messages[0].content.text

    required_resources = [
        "knowledge://vocabulary",
        "knowledge://subgenre-culture",
        "knowledge://set-dynamics",
        "knowledge://dancefloor-psychology",
        "library://snapshot",
    ]
    for res in required_resources:
        assert res in user_content, f"Prompt missing resource reference: {res}"


@pytest.mark.asyncio
async def test_prompt_with_goal():
    """Passing goal embeds it in the user message."""
    from app.controllers.prompts.workflows.dj_expert_session import dj_expert_session

    result = dj_expert_session(goal="dark and driving, 90 minutes, after midnight")
    user_text = result.messages[0].content.text
    assert "dark and driving" in user_text
    assert "90 minutes" in user_text


@pytest.mark.asyncio
async def test_assistant_message_is_dj_style():
    """Assistant message demonstrates DJ-style response, not database-style."""
    from app.controllers.prompts.workflows.dj_expert_session import dj_expert_session

    result = dj_expert_session()
    assistant_content = result.messages[1].content.text
    assert len(assistant_content) > 50
    assert "SELECT" not in assistant_content
