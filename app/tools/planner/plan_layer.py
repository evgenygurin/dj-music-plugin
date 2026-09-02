from fastmcp.tools import tool
from pydantic import Field

from app.schemas.planner import DeckAssignment, PlanLayerResult, Role

DEFAULT_ROLES = {
    2: [Role.FOUNDATION, Role.INCOMING],
    4: [Role.FOUNDATION, Role.INCOMING, Role.PERCUSSION, Role.TEXTURE],
    6: [Role.FOUNDATION, Role.INCOMING, Role.PERCUSSION, Role.TEXTURE, Role.VOICE, Role.BRIDGE],
}


@tool
def plan_layer(
    n_decks: int = Field(ge=2, le=12, description="Number of decks (2-12)"),
    roles: list[Role] | None = Field(default=None, description="Custom role assignments"),
) -> PlanLayerResult:
    if roles is None:
        roles = DEFAULT_ROLES.get(n_decks) or (DEFAULT_ROLES[6] + [Role.TEXTURE] * (n_decks - 6))

    if not 2 <= n_decks <= 12:
        raise ValueError(f"n_decks must be between 2 and 12, got {n_decks}")

    if len(roles) != n_decks:
        raise ValueError(f"Number of roles ({len(roles)}) must match n_decks ({n_decks})")

    low_roles = {Role.FOUNDATION, Role.INCOMING}
    low_indices = [i for i, r in enumerate(roles) if r in low_roles]
    if len(low_indices) == 0:
        raise ValueError("At least one LOW role (FOUNDATION or INCOMING) required")

    decks = []
    for i, role in enumerate(roles):
        owns_low = i == low_indices[0]
        decks.append(DeckAssignment(role=role, owns_low=owns_low))

    return PlanLayerResult(decks=decks, invariant="one LOW")
