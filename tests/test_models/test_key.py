"""Tests for Key and KeyEdge models."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from dj_music.core.constants import CAMELOT_KEYS
from dj_music.models.key import Key, KeyEdge


class TestKey:
    """Tests for the Key model."""

    async def test_create_key(self, db):
        key = Key(key_code=14, pitch_class=9, mode=0, name="A minor", camelot="8A")
        db.add(key)
        await db.flush()

        result = await db.get(Key, 14)
        assert result is not None
        assert result.key_code == 14
        assert result.pitch_class == 9
        assert result.mode == 0
        assert result.name == "A minor"
        assert result.camelot == "8A"

    async def test_create_all_24_keys(self, db):
        for code, (camelot, name) in CAMELOT_KEYS.items():
            mode = 1 if camelot.endswith("B") else 0
            pitch_class = code % 12
            db.add(
                Key(key_code=code, pitch_class=pitch_class, mode=mode, name=name, camelot=camelot)
            )
        await db.flush()

        result = await db.execute(select(Key))
        keys = result.scalars().all()
        assert len(keys) == 24

    async def test_key_code_range_lower_bound(self, db):
        key = Key(key_code=0, pitch_class=0, mode=0, name="Ab minor", camelot="1A")
        db.add(key)
        await db.flush()
        assert key.key_code == 0

    async def test_key_code_range_upper_bound(self, db):
        key = Key(key_code=23, pitch_class=11, mode=1, name="E major", camelot="12B")
        db.add(key)
        await db.flush()
        assert key.key_code == 23

    async def test_key_code_out_of_range_raises(self, db):
        key = Key(key_code=24, pitch_class=0, mode=0, name="invalid", camelot="XX")
        db.add(key)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_key_code_negative_raises(self, db):
        key = Key(key_code=-1, pitch_class=0, mode=0, name="invalid", camelot="XX")
        db.add(key)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_mode_invalid_raises(self, db):
        key = Key(key_code=0, pitch_class=0, mode=2, name="invalid", camelot="XX")
        db.add(key)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_pitch_class_out_of_range_raises(self, db):
        key = Key(key_code=0, pitch_class=12, mode=0, name="invalid", camelot="XX")
        db.add(key)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_repr(self, db):
        key = Key(key_code=14, pitch_class=9, mode=0, name="A minor", camelot="8A")
        assert "8A" in repr(key)
        assert "A minor" in repr(key)


class TestKeyEdge:
    """Tests for the KeyEdge model."""

    async def _seed_keys(self, db):
        """Create two keys for FK references."""
        k1 = Key(key_code=14, pitch_class=9, mode=0, name="A minor", camelot="8A")
        k2 = Key(key_code=15, pitch_class=0, mode=1, name="C major", camelot="8B")
        db.add_all([k1, k2])
        await db.flush()
        return k1, k2

    async def test_create_edge(self, db):
        k1, k2 = await self._seed_keys(db)
        edge = KeyEdge(
            from_key_code=k1.key_code,
            to_key_code=k2.key_code,
            distance=0,
            weight=1.0,
            rule_name="relative_major",
        )
        db.add(edge)
        await db.flush()

        assert edge.id is not None
        assert edge.from_key_code == 14
        assert edge.to_key_code == 15
        assert edge.distance == 0
        assert edge.weight == 1.0
        assert edge.rule_name == "relative_major"

    async def test_edge_fk_relationship(self, db):
        k1, k2 = await self._seed_keys(db)
        edge = KeyEdge(
            from_key_code=k1.key_code,
            to_key_code=k2.key_code,
            distance=1,
            weight=0.8,
            rule_name="adjacent",
        )
        db.add(edge)
        await db.flush()

        # Refresh to load relationships
        await db.refresh(k1, ["edges_from"])
        assert len(k1.edges_from) == 1
        assert k1.edges_from[0].to_key_code == 15

    async def test_edge_invalid_fk_raises(self, db):
        edge = KeyEdge(
            from_key_code=99,
            to_key_code=98,
            distance=1,
            weight=0.5,
            rule_name="invalid",
        )
        db.add(edge)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_repr(self, db):
        edge = KeyEdge(
            from_key_code=14,
            to_key_code=15,
            distance=0,
            weight=1.0,
            rule_name="relative_major",
        )
        r = repr(edge)
        assert "from=14" in r
        assert "to=15" in r
