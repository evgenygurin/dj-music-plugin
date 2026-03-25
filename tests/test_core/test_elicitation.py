"""Tests for elicitation utilities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from app.core.elicitation import safe_choice, safe_confirm, safe_elicit


class SampleSchema(BaseModel):
    """Sample Pydantic schema for testing."""

    name: str
    age: int


class MockElicitResult:
    """Mock ElicitResult for testing."""

    def __init__(self, action: str, data: BaseModel | None = None):
        self.action = action
        self.data = data


@pytest.fixture
def mock_ctx():
    """Create mock FastMCP context."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.elicit = AsyncMock()
    return ctx


# ── safe_elicit tests ──────────────────────────────


@pytest.mark.asyncio
async def test_safe_elicit_accept(mock_ctx):
    """Test elicitation with user accepting."""
    mock_ctx.elicit.return_value = MockElicitResult(
        action="accept", data=SampleSchema(name="Alice", age=30)
    )

    action, data = await safe_elicit(
        mock_ctx, "Enter your info", SampleSchema, default_action="decline"
    )

    assert action == "accept"
    assert data is not None
    assert data.name == "Alice"
    assert data.age == 30
    mock_ctx.elicit.assert_called_once()


@pytest.mark.asyncio
async def test_safe_elicit_decline(mock_ctx):
    """Test elicitation with user declining."""
    mock_ctx.elicit.return_value = MockElicitResult(action="decline")

    action, data = await safe_elicit(
        mock_ctx, "Enter your info", SampleSchema, default_action="decline"
    )

    assert action == "decline"
    assert data is None


@pytest.mark.asyncio
async def test_safe_elicit_cancel(mock_ctx):
    """Test elicitation with user cancelling."""
    mock_ctx.elicit.return_value = MockElicitResult(action="cancel")

    action, data = await safe_elicit(
        mock_ctx, "Enter your info", SampleSchema, default_action="decline"
    )

    assert action == "cancel"
    assert data is None


@pytest.mark.asyncio
async def test_safe_elicit_no_context():
    """Test elicitation without context (testing mode)."""
    action, data = await safe_elicit(
        None, "Enter your info", SampleSchema, default_action="decline", default_data=None
    )

    assert action == "decline"
    assert data is None


@pytest.mark.asyncio
async def test_safe_elicit_fallback_on_error(mock_ctx):
    """Test graceful fallback when elicitation fails."""
    mock_ctx.elicit.side_effect = Exception("Elicitation not supported")

    default_data = SampleSchema(name="Default", age=0)
    action, data = await safe_elicit(
        mock_ctx,
        "Enter your info",
        SampleSchema,
        default_action="accept",
        default_data=default_data,
    )

    assert action == "accept"
    assert data == default_data
    mock_ctx.info.assert_called_once()
    assert "doesn't support elicitation" in mock_ctx.info.call_args[0][0]


@pytest.mark.asyncio
async def test_safe_elicit_fallback_decline_default(mock_ctx):
    """Test fallback with decline default."""
    mock_ctx.elicit.side_effect = Exception("Not supported")

    action, data = await safe_elicit(
        mock_ctx, "Enter your info", SampleSchema, default_action="decline"
    )

    assert action == "decline"
    assert data is None


# ── safe_confirm tests ──────────────────────────────


@pytest.mark.asyncio
async def test_safe_confirm_true(mock_ctx):
    """Test confirmation with user confirming."""

    class ConfirmSchema(BaseModel):
        confirm: bool

    mock_ctx.elicit.return_value = MockElicitResult(
        action="accept", data=ConfirmSchema(confirm=True)
    )

    result = await safe_confirm(mock_ctx, "Are you sure?", default=False)

    assert result is True


@pytest.mark.asyncio
async def test_safe_confirm_false(mock_ctx):
    """Test confirmation with user declining."""

    class ConfirmSchema(BaseModel):
        confirm: bool

    mock_ctx.elicit.return_value = MockElicitResult(
        action="accept", data=ConfirmSchema(confirm=False)
    )

    result = await safe_confirm(mock_ctx, "Are you sure?", default=True)

    assert result is False


@pytest.mark.asyncio
async def test_safe_confirm_cancel(mock_ctx):
    """Test confirmation with user cancelling."""
    mock_ctx.elicit.return_value = MockElicitResult(action="cancel")

    result = await safe_confirm(mock_ctx, "Are you sure?", default=False)

    assert result is None


@pytest.mark.asyncio
async def test_safe_confirm_fallback_default_true(mock_ctx):
    """Test confirmation fallback with default=True."""
    mock_ctx.elicit.side_effect = Exception("Not supported")

    result = await safe_confirm(mock_ctx, "Are you sure?", default=True)

    assert result is True  # Uses default


@pytest.mark.asyncio
async def test_safe_confirm_fallback_default_false(mock_ctx):
    """Test confirmation fallback with default=False."""
    mock_ctx.elicit.side_effect = Exception("Not supported")

    result = await safe_confirm(mock_ctx, "Are you sure?", default=False)

    assert result is False  # Uses default


# ── safe_choice tests ───────────────────────────────


@pytest.mark.asyncio
async def test_safe_choice_select_first(mock_ctx):
    """Test choice selection with user selecting first option."""
    from enum import Enum

    # Mock elicit to return first choice
    def mock_elicit(message, response_type):
        # Simulate user selecting the first choice
        ChoiceEnum = response_type.__annotations__["choice"]
        for member in ChoiceEnum:
            result_data = response_type(choice=member)
            return MockElicitResult(action="accept", data=result_data)

    mock_ctx.elicit.side_effect = mock_elicit

    result = await safe_choice(
        mock_ctx, "Pick one", choices=["option_a", "option_b", "option_c"], default="option_a"
    )

    assert result == "option_a"


@pytest.mark.asyncio
async def test_safe_choice_cancel(mock_ctx):
    """Test choice with user cancelling."""
    mock_ctx.elicit.return_value = MockElicitResult(action="cancel")

    result = await safe_choice(
        mock_ctx, "Pick one", choices=["option_a", "option_b"], default="option_a"
    )

    assert result is None


@pytest.mark.asyncio
async def test_safe_choice_invalid_default():
    """Test choice with invalid default raises ValueError."""
    with pytest.raises(ValueError, match="must be one of"):
        await safe_choice(None, "Pick one", choices=["a", "b"], default="invalid")


@pytest.mark.asyncio
async def test_safe_choice_fallback_to_default(mock_ctx):
    """Test choice fallback when elicitation not supported."""
    mock_ctx.elicit.side_effect = Exception("Not supported")

    result = await safe_choice(
        mock_ctx, "Pick one", choices=["option_a", "option_b"], default="option_b"
    )

    assert result == "option_b"


@pytest.mark.asyncio
async def test_safe_choice_no_context_with_default():
    """Test choice without context uses default."""
    result = await safe_choice(
        None, "Pick one", choices=["option_a", "option_b"], default="option_a"
    )

    assert result == "option_a"


@pytest.mark.asyncio
async def test_safe_choice_decline_returns_default(mock_ctx):
    """Test choice decline returns default."""
    mock_ctx.elicit.return_value = MockElicitResult(action="decline")

    result = await safe_choice(
        mock_ctx, "Pick one", choices=["option_a", "option_b"], default="option_b"
    )

    assert result == "option_b"
