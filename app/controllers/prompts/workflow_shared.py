"""Shared helpers for MCP workflow prompts (FastMCP ``@prompt``).

Runtime-checked API (fastmcp 3.2.x): ``Message(content, role='user'|'assistant')``,
``PromptResult(messages=[...], description='...')``.

External ``search_docs`` had no excerpts in this environment; helpers mirror the
installed package behaviour only.
"""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult

# Increment when prompt semantics or tool references change meaningfully.
WORKFLOW_PROMPT_VERSION = "1.2"


def message_user(content: str) -> Message:
    return Message(content, role="user")


def message_assistant(content: str) -> Message:
    return Message(content, role="assistant")


def prompt_pair(user_content: str, assistant_content: str) -> list[Message]:
    """Two-turn pattern: instructions (user) + kickoff line (assistant)."""
    return [message_user(user_content), message_assistant(assistant_content)]


def make_prompt_result(messages: list[Message], description: str) -> PromptResult:
    return PromptResult(messages=messages, description=description)
