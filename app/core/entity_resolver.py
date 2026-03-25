from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

from fastmcp.server.context import Context

from app.core.elicitation import safe_choice

T = TypeVar("T")


@dataclass(frozen=True)
class EntityRef:
    """Parsed entity reference."""

    type: Literal["id", "ym_id", "query"]
    value: Any  # int for id, str for ym_id/query


@dataclass
class EntityMatch(Generic[T]):
    """A single entity match result."""

    entity: T
    score: float  # 0.0-1.0 relevance score
    match_field: str  # which field matched (name, title, etc.)


@dataclass
class ResolvedEntity(Generic[T]):
    """Result of entity resolution with optional alternatives."""

    entity: T
    confidence: float  # 0.0-1.0
    alternatives: list[EntityMatch[T]]  # other possible matches
    resolution_method: Literal["exact_id", "ym_id", "text_search", "elicitation"]


def parse_entity_ref(ref: int | str) -> EntityRef:
    """Parse flexible entity reference.

    Supports: numeric ID (42 or "42"), prefixed ("ym:12345"), text query ("Aphex Twin").
    Raises ValueError if empty.
    """
    if isinstance(ref, int):
        return EntityRef(type="id", value=ref)

    ref_str = str(ref).strip()
    if not ref_str:
        raise ValueError("Entity reference cannot be empty")

    # Try numeric
    try:
        return EntityRef(type="id", value=int(ref_str))
    except ValueError:
        pass

    # Try ym: prefix
    if ref_str.startswith("ym:"):
        return EntityRef(type="ym_id", value=ref_str[3:])

    # Default: text query
    return EntityRef(type="query", value=ref_str)


class EntityResolver(Generic[T]):
    """Resolve entity references with elicitation for ambiguous queries.

    Example:
        >>> resolver = EntityResolver(
        ...     get_by_id=track_repo.get_by_id,
        ...     get_by_ym_id=track_repo.get_by_ym_id,
        ...     search_by_query=track_repo.search,
        ...     get_display_name=lambda t: t.title,
        ... )
        >>> result = await resolver.resolve(
        ...     ref="Aphex Twin",
        ...     ctx=ctx,
        ...     elicit_on_ambiguous=True,
        ... )
        >>> if result:
        ...     print(f"Resolved to: {result.entity.title}")
    """

    def __init__(
        self,
        get_by_id: Any,  # async (int) -> T | None
        get_by_ym_id: Any | None = None,  # async (str) -> T | None
        search_by_query: Any | None = None,  # async (str) -> list[EntityMatch[T]]
        get_display_name: Any | None = None,  # (T) -> str
    ):
        self._get_by_id = get_by_id
        self._get_by_ym_id = get_by_ym_id
        self._search_by_query = search_by_query
        self._get_display_name = get_display_name or (lambda e: str(e))

    async def resolve(
        self,
        ref: int | str | None,
        ctx: Context | None = None,
        elicit_on_ambiguous: bool = True,
        max_alternatives: int = 5,
    ) -> ResolvedEntity[T] | None:
        """Resolve entity reference with optional elicitation.

        Args:
            ref: Entity reference (ID, ym:ID, or text query)
            ctx: FastMCP context for elicitation
            elicit_on_ambiguous: Use elicitation when multiple matches found
            max_alternatives: Max alternatives to show in elicitation

        Returns:
            ResolvedEntity if found, None if not found or user cancelled

        Raises:
            ValueError: If ref is None or empty
        """
        if ref is None:
            return None

        entity_ref = parse_entity_ref(ref)

        # ── Exact ID lookup ──
        if entity_ref.type == "id":
            entity = await self._get_by_id(entity_ref.value)
            if entity:
                return ResolvedEntity(
                    entity=entity,
                    confidence=1.0,
                    alternatives=[],
                    resolution_method="exact_id",
                )
            return None

        # ── YM ID lookup ──
        if entity_ref.type == "ym_id" and self._get_by_ym_id:
            entity = await self._get_by_ym_id(entity_ref.value)
            if entity:
                return ResolvedEntity(
                    entity=entity,
                    confidence=1.0,
                    alternatives=[],
                    resolution_method="ym_id",
                )
            return None

        # ── Text search with elicitation ──
        if entity_ref.type == "query" and self._search_by_query:
            matches = await self._search_by_query(entity_ref.value)

            if not matches:
                return None

            # Single high-confidence match → return directly
            if len(matches) == 1:
                return ResolvedEntity(
                    entity=matches[0].entity,
                    confidence=matches[0].score,
                    alternatives=matches[1:max_alternatives],
                    resolution_method="text_search",
                )

            # Multiple matches → elicit if enabled
            if elicit_on_ambiguous and ctx:
                top_matches = matches[:max_alternatives]
                choices = [self._get_display_name(m.entity) for m in top_matches]

                selected = await safe_choice(
                    ctx,
                    message=f"Found {len(matches)} matches for '{entity_ref.value}'. Which one?",
                    choices=choices,
                    default=choices[0] if choices else None,
                )

                if selected is None:
                    # User cancelled
                    return None

                # Find selected entity
                for i, choice in enumerate(choices):
                    if choice == selected:
                        return ResolvedEntity(
                            entity=top_matches[i].entity,
                            confidence=top_matches[i].score,
                            alternatives=[m for j, m in enumerate(top_matches) if j != i],
                            resolution_method="elicitation",
                        )

            # No elicitation or fallback → return best match
            return ResolvedEntity(
                entity=matches[0].entity,
                confidence=matches[0].score,
                alternatives=matches[1:max_alternatives],
                resolution_method="text_search",
            )

        return None
