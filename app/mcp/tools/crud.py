"""Set CRUD tools — list, get, manage (3 tools, tag: core)."""

from __future__ import annotations

from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select

from app.core.schemas import PaginatedResponse, SetSummary
from app.mcp.dependencies import get_db_session
from app.models.set import DjSet, SetConstraint, SetFeedback, SetItem, SetVersion
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.services.track_service import TrackService


def _set_summary(s: DjSet, version: SetVersion | None = None) -> dict[str, Any]:
    """Convert DjSet model to SetSummary dict."""
    return SetSummary(
        id=s.id,
        name=s.name,
        track_count=len(version.items) if version and version.items else 0,
        template=s.template_name,
        latest_score=version.quality_score if version else None,
    ).model_dump()


# ── 7. list_sets ────────────────────────────────────


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_sets(
    template: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List DJ sets with optional template filter and cursor pagination."""
    async with get_db_session() as session:
        repo = SetRepository(session)

        stmt = select(DjSet)
        if template is not None:
            stmt = stmt.where(DjSet.template_name == template)

        page = await repo._paginate(stmt, limit=limit, cursor=cursor)

        items = []
        for s in page.items:
            latest = await repo.get_latest_version(s.id)
            items.append(
                SetSummary(
                    id=s.id,
                    name=s.name,
                    track_count=0,
                    template=s.template_name,
                    latest_score=latest.quality_score if latest else None,
                )
            )

        return PaginatedResponse[SetSummary](
            items=items,
            next_cursor=page.next_cursor,
            total=page.total,
        ).model_dump()


# ── 8. get_set ──────────────────────────────────────


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_set(
    id: int | None = None,
    query: str | None = None,
    view: str = "summary",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get set details by id or query. view: summary|tracks|transitions|full."""
    if id is None and query is None:
        raise ToolError("Provide id or query")

    async with get_db_session() as session:
        repo = SetRepository(session)

        dj_set: DjSet | None = None
        if id is not None:
            dj_set = await repo.get_by_id(id)
        elif query is not None:
            stmt = select(DjSet).where(DjSet.name.ilike(f"%{query}%")).limit(1)
            result = await session.execute(stmt)
            dj_set = result.scalar_one_or_none()

        if dj_set is None:
            raise ToolError("Set not found")

        latest = await repo.get_latest_version(dj_set.id)
        response = _set_summary(dj_set, latest)

        if view in ("tracks", "full") and latest:
            stmt_items = (
                select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
            )
            result = await session.execute(stmt_items)
            items = list(result.scalars().all())

            track_repo = TrackRepository(session)
            tracks = []
            for item in items:
                t = await track_repo.get_by_id(item.track_id)
                if t:
                    tracks.append(
                        {
                            "position": item.sort_index,
                            "pinned": item.pinned,
                            **TrackService.to_brief(t).model_dump(),
                        }
                    )
            response["tracks"] = tracks

        if view in ("transitions", "full") and latest:
            response["version_id"] = latest.id
            response["version_label"] = latest.label
            response["quality_score"] = latest.quality_score

        return response


# ── 9. manage_set ───────────────────────────────────


@tool(tags={"core"}, annotations={"readOnlyHint": False})
async def manage_set(
    action: str,
    data: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Manage DJ sets. Actions: create, update, delete, add/remove constraint, add feedback."""
    valid = ("create", "update", "delete", "add_constraint", "remove_constraint", "add_feedback")
    if action not in valid:
        raise ToolError(f"Unknown action: {action}. Valid: {', '.join(valid)}")

    async with get_db_session() as session:
        repo = SetRepository(session)

        if action == "create":
            if not data or "name" not in data:
                raise ToolError("data.name required for create")
            dj_set = DjSet(
                name=data["name"],
                description=data.get("description"),
                target_duration_ms=data.get("target_duration_ms"),
                template_name=data.get("template"),
            )
            dj_set = await repo.create(dj_set)
            await session.commit()
            return _set_summary(dj_set)

        # add_feedback doesn't require set_id
        if action == "add_feedback":
            if not data or "version_id" not in data or "rating" not in data:
                raise ToolError("data.version_id and data.rating required")
            feedback = SetFeedback(
                version_id=data["version_id"],
                rating=data["rating"],
                feedback_type=data.get("feedback_type", "general"),
                notes=data.get("notes"),
                set_item_id=data.get("set_item_id"),
            )
            session.add(feedback)
            await session.flush()
            await session.commit()
            return {"feedback_id": feedback.id, "version_id": data["version_id"]}

        set_id = (data or {}).get("id")
        if set_id is None:
            raise ToolError("data.id required")

        if action == "delete":
            deleted = await repo.delete(set_id)
            await session.commit()
            return {"deleted": deleted, "id": set_id}

        dj_set = await repo.get_by_id(set_id)
        if dj_set is None:
            raise ToolError(f"Set {set_id} not found")

        if action == "update":
            if data:
                if "name" in data:
                    dj_set.name = data["name"]
                if "description" in data:
                    dj_set.description = data["description"]
                if "template" in data:
                    dj_set.template_name = data["template"]
            await repo.update(dj_set)
            await session.commit()
            return _set_summary(dj_set)

        if action == "add_constraint":
            if not data or "constraint_type" not in data or "constraint_value" not in data:
                raise ToolError("data.constraint_type and data.constraint_value required")
            import json as _json

            value = data["constraint_value"]
            constraint = SetConstraint(
                set_id=set_id,
                constraint_type=data["constraint_type"],
                constraint_value=_json.dumps(value) if isinstance(value, dict | list) else value,
            )
            session.add(constraint)
            await session.flush()
            await session.commit()
            return {"constraint_id": constraint.id, "set_id": set_id}

        if action == "remove_constraint":
            constraint_id = (data or {}).get("constraint_id")
            if constraint_id is None:
                raise ToolError("data.constraint_id required")
            stmt = select(SetConstraint).where(SetConstraint.id == constraint_id)
            result = await session.execute(stmt)
            constraint = result.scalar_one_or_none()
            if constraint is None:
                raise ToolError(f"Constraint {constraint_id} not found")
            await session.delete(constraint)
            await session.flush()
            await session.commit()
            return {"removed": True, "constraint_id": constraint_id}

        raise ToolError("Unreachable")

