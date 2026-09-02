from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    FOUNDATION = "FOUNDATION"
    INCOMING = "INCOMING"
    PERCUSSION = "PERCUSSION"
    TEXTURE = "TEXTURE"
    VOICE = "VOICE"
    BRIDGE = "BRIDGE"


class DeckAssignment(BaseModel):
    role: Role
    owns_low: bool = False


class PlanLayerResult(BaseModel):
    decks: list[DeckAssignment]
    invariant: str = "one LOW"
