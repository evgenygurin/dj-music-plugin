"""Elicitation utilities for safe user interaction with fallback handling."""

from __future__ import annotations

from fastmcp.server.context import Context
from pydantic import BaseModel


async def safe_elicit[T: BaseModel](
    ctx: Context | None,
    message: str,
    response_type: type[T],
    default_action: str = "decline",
    default_data: T | None = None,
) -> tuple[str, T | None]:
    """Safe elicitation with fallback when client doesn't support it.

    Args:
        ctx: FastMCP context (may be None in tests)
        message: Message to display to user
        response_type: Pydantic model type for structured response
        default_action: Action to use if elicitation fails ("accept", "decline", "cancel")
        default_data: Data to use if default_action="accept" and elicitation fails

    Returns:
        Tuple of (action, data) where:
        - action is "accept", "decline", or "cancel"
        - data is the Pydantic model instance if action="accept", else None

    Example:
        >>> from pydantic import BaseModel
        >>> class Choice(BaseModel):
        ...     option: str
        >>> action, data = await safe_elicit(
        ...     ctx,
        ...     "Choose an option",
        ...     Choice,
        ...     default_action="decline"
        ... )
        >>> if action == "accept":
        ...     print(f"User chose: {data.option}")
        ... elif action == "decline":
        ...     print("User declined")
        ... else:
        ...     print("User cancelled")
    """
    if ctx is None:
        # No context → testing environment or non-MCP call
        return (default_action, default_data)

    try:
        result = await ctx.elicit(message, response_type=response_type)  # type: ignore[arg-type]

        if result.action == "accept":
            return ("accept", result.data)  # type: ignore[return-value]
        elif result.action == "decline":
            return ("decline", None)
        else:  # cancel
            return ("cancel", None)

    except Exception:
        # Elicitation not supported or failed → graceful fallback
        if ctx:
            await ctx.info(
                f"⚠️ User input required but client doesn't support elicitation. "
                f"Using default: {default_action}"
            )
        return (default_action, default_data)


async def safe_confirm(
    ctx: Context | None,
    message: str,
    default: bool = False,
) -> bool | None:
    """Safe yes/no confirmation with fallback.

    Args:
        ctx: FastMCP context
        message: Confirmation message
        default: Default choice if elicitation not supported

    Returns:
        True if confirmed, False if declined, None if cancelled
    """

    class ConfirmSchema(BaseModel):
        confirm: bool

    action, data = await safe_elicit(
        ctx,
        message,
        ConfirmSchema,
        default_action="accept" if default else "decline",
        default_data=ConfirmSchema(confirm=default) if default else None,
    )

    if action == "accept" and data:
        return data.confirm
    elif action == "decline":
        return False
    else:  # cancel
        return None


async def safe_choice(
    ctx: Context | None,
    message: str,
    choices: list[str],
    default: str | None = None,
) -> str | None:
    """Safe single-choice selection with fallback.

    Args:
        ctx: FastMCP context
        message: Choice prompt message
        choices: List of valid choices
        default: Default choice if elicitation not supported (must be in choices)

    Returns:
        Selected choice string, or None if cancelled

    Raises:
        ValueError: If default not in choices
    """
    if default is not None and default not in choices:
        raise ValueError(f"Default '{default}' must be one of {choices}")

    from enum import Enum

    # Dynamically create Enum for choices
    choice_members = {c.upper().replace(" ", "_"): c for c in choices}
    ChoiceEnum = Enum("ChoiceEnum", choice_members)  # type: ignore[misc]  # noqa: N806

    class ChoiceSchema(BaseModel):
        choice: ChoiceEnum

    default_data = None
    if default:
        # Find matching enum member
        for member in ChoiceEnum:
            if member.value == default:
                default_data = ChoiceSchema(choice=member)
                break
                break

    action, data = await safe_elicit(
        ctx,
        message,
        ChoiceSchema,
        default_action="accept" if default else "decline",
        default_data=default_data,
    )

    if action == "accept" and data:
        return data.choice.value  # type: ignore
    elif action == "cancel":
        return None
    else:  # decline
        return default
