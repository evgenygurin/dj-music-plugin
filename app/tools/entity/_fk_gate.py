"""Generic FK existence validation for ``entity_create`` / ``entity_update``.

Each entity declares its FK columns once in
``EntityConfig.fk_constraints`` (see ``app.registry.entity``). This
helper iterates the declarations and verifies the referenced row
exists in the target repository — converting what would otherwise be
an opaque ``ForeignKeyViolationError`` (PostgreSQL) or silently-kept
orphan row (SQLite, FK enforcement off by default) into a typed
``ValidationError`` naming the bad id.

Message shape mirrors the per-entity branches the previous rounds
had:

* Single-FK entity (e.g. ``set.source_playlist_id``):
  ``"source_playlist_id N does not reference an existing playlist"``

* Multi-FK entity (e.g. ``track_affinity``,
  ``transition_history``) — uses the grouped "entity references
  missing target(s): field=N, …" shape, even when only one side is
  missing, because the per-FK fields and the singular target name are
  intertwined.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from app.registry.entity import EntityConfig
from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import ValidationError


async def validate_fk_constraints(
    uow: UnitOfWork,
    config: EntityConfig,
    validated: BaseModel,
    *,
    partial_keys: Iterable[str] | None = None,
) -> None:
    """Verify every declared FK reference exists.

    ``partial_keys`` — when set (the ``entity_update`` path), only FK
    fields actually present in the user's payload are checked.
    ``None`` (the ``entity_create`` path) checks every declared FK.
    """
    if not config.fk_constraints:
        return

    partial_set = set(partial_keys) if partial_keys is not None else None

    # missing: list of (field, value, target_singular)
    missing: list[tuple[str, Any, str]] = []
    for fk in config.fk_constraints:
        if partial_set is not None and fk.field not in partial_set:
            continue
        value = getattr(validated, fk.field, None)
        if value is None:
            continue
        repo = getattr(uow, fk.target_repo, None)
        if repo is None:
            # Defensive: a misconfigured target_repo should fail loudly
            # at startup-ish time (first use), not silently no-op.
            raise RuntimeError(
                f"FK constraint {config.name}.{fk.field} → repo "
                f"{fk.target_repo!r} not on UnitOfWork"
            )
        if await repo.get(value) is None:
            missing.append((fk.field, value, fk.target_singular))

    if not missing:
        return

    # Single-FK entity: legacy single-line shape.
    if len(config.fk_constraints) == 1:
        field, value, target = missing[0]
        raise ValidationError(
            f"{field} {value} does not reference an existing {target}",
            details={field: value},
        )

    # Multi-FK entity: grouped shape "ENTITY references missing TARGET(s): ...".
    # Group by target_singular so different targets get separate clauses.
    by_target: dict[str, list[tuple[str, Any]]] = {}
    for field, value, target in missing:
        by_target.setdefault(target, []).append((field, value))

    parts: list[str] = []
    for target, refs in by_target.items():
        items = ", ".join(f"{f}={v}" for f, v in refs)
        parts.append(f"missing {target}(s): {items}")

    raise ValidationError(
        f"{config.name} references {'; '.join(parts)}",
        details={f: v for f, v, _ in missing},
    )
