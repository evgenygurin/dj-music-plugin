"""Idempotent database seed for reference data.

Seeds: 24 keys (Camelot wheel), key_edges (compatibility graph), 4 providers.
Called once at server startup in db_lifespan. Skips if data already exists.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dj_music.core.camelot import camelot_distance
from dj_music.core.constants import CAMELOT_KEYS, Provider
from dj_music.models.ingestion import ProviderModel
from dj_music.models.key import Key, KeyEdge

logger = logging.getLogger(__name__)

# Pitch class mapping: key_name → pitch_class (0-11)
# Derived from standard music theory (C=0, C#=1, ..., B=11)
_PITCH_CLASSES: dict[str, int] = {
    "C": 0,
    "D♭": 1,
    "D": 2,
    "E♭": 3,
    "E": 4,
    "F": 5,
    "F♯": 6,
    "G": 7,
    "A♭": 8,
    "A": 9,
    "B♭": 10,
    "B": 11,
}


def _extract_pitch_class(key_name: str) -> int:
    """Extract pitch class from key name like 'A minor' or 'F♯ major'."""
    root = key_name.split()[0]  # "A♭ minor" → "A♭"
    return _PITCH_CLASSES.get(root, 0)


def _edge_rule_name(distance: int, mode_a: int, mode_b: int) -> str:
    """Determine rule name based on distance and mode relationship."""
    if distance == 0:
        return "same_key"
    if distance == 1:
        return "relative_major_minor" if mode_a != mode_b else "adjacent"
    if distance == 2:
        return "energy_boost"
    if distance <= 4:
        return "tension"
    return "clash"


async def seed_reference_data(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Seed keys, key_edges, and providers if not already populated.

    Idempotent: checks COUNT before inserting. Safe to call on every startup.
    """
    async with session_factory() as session:
        # ── Check if already seeded ──
        key_count = (await session.execute(select(func.count()).select_from(Key))).scalar() or 0
        if key_count >= 24:
            logger.debug("Reference data already seeded (%d keys), skipping", key_count)
            return

        logger.info("Seeding reference data: 24 keys, key_edges, 4 providers...")

        # ── Keys (24) ──
        for code, (camelot, name) in CAMELOT_KEYS.items():
            mode = 1 if camelot.endswith("B") else 0  # A=minor(0), B=major(1)
            pitch_class = _extract_pitch_class(name)
            session.add(
                Key(
                    key_code=code,
                    pitch_class=pitch_class,
                    mode=mode,
                    name=name,
                    camelot=camelot,
                )
            )
        await session.flush()

        # ── Key Edges (24x24 = 576 pairs) ──
        for a in range(24):
            mode_a = a % 2
            for b in range(24):
                mode_b = b % 2
                dist = camelot_distance(a, b)
                weight = 1.0 / max(1, dist)
                rule = _edge_rule_name(dist, mode_a, mode_b)
                session.add(
                    KeyEdge(
                        from_key_code=a,
                        to_key_code=b,
                        distance=dist,
                        weight=round(weight, 4),
                        rule_name=rule,
                    )
                )
        await session.flush()

        # ── Providers (4) ──
        provider_count = (
            await session.execute(select(func.count()).select_from(ProviderModel))
        ).scalar() or 0
        if provider_count == 0:
            for p in Provider:
                session.add(ProviderModel(name=p.value))
            await session.flush()

        await session.commit()
        logger.info(
            "Seeded: 24 keys, %d key_edges, %d providers",
            24 * 24,
            len(Provider),
        )
