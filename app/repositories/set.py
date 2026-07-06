"""Set repository + set-version helpers."""

from __future__ import annotations

from sqlalchemy import func, select

from app.domain.render.models import TrackInput
from app.models.set import DjSet, DjSetItem, DjSetVersion
from app.models.track import Track
from app.repositories.base import BaseRepository
from app.shared.errors import ValidationError


class SetRepository(BaseRepository[DjSet]):
    model = DjSet

    async def version_count(self, set_id: int) -> int:
        stmt = select(func.count()).select_from(DjSetVersion).where(DjSetVersion.set_id == set_id)
        return int(await self.session.scalar(stmt) or 0)

    async def latest_version(self, set_id: int) -> DjSetVersion | None:
        stmt = (
            select(DjSetVersion)
            .where(DjSetVersion.set_id == set_id)
            .order_by(DjSetVersion.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]


class SetVersionRepository(BaseRepository[DjSetVersion]):
    model = DjSetVersion

    async def list_for_set(self, set_id: int) -> list[DjSetVersion]:
        """All versions of a set, oldest first (no pagination cap — a set
        has a handful of versions). Backs
        ``entity_get(set, id, include_relations=["versions"])``."""
        stmt = select(DjSetVersion).where(DjSetVersion.set_id == set_id).order_by(DjSetVersion.id)
        return list((await self.session.execute(stmt)).scalars())

    async def get_items(self, version_id: int) -> list[DjSetItem]:
        stmt = (
            select(DjSetItem)
            .where(DjSetItem.version_id == version_id)
            .order_by(DjSetItem.sort_index)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def create_items(self, version_id: int, track_order: list[int]) -> int:
        # Verify every track_id exists before bulk-inserting; otherwise SQLite
        # (tests, default FK enforcement off) silently writes orphans and
        # PostgreSQL raises an opaque foreign-key violation. A single batch
        # ``SELECT id IN (...)`` is cheap and produces a typed
        # ValidationError naming the bogus ids.
        if track_order:
            unique_ids = list(set(track_order))
            stmt = select(Track.id).where(Track.id.in_(unique_ids))
            existing = {row for (row,) in (await self.session.execute(stmt)).all()}
            missing = [tid for tid in unique_ids if tid not in existing]
            if missing:
                raise ValidationError(
                    f"track_order references unknown track id(s) {sorted(missing)!r}; "
                    f"verified {len(existing)}/{len(unique_ids)} exist",
                    details={"missing_track_ids": sorted(missing)},
                )
        items = [
            DjSetItem(version_id=version_id, track_id=tid, sort_index=i)
            for i, tid in enumerate(track_order)
        ]
        self.session.add_all(items)
        await self.session.flush()
        return len(items)

    async def get_latest(self, set_id: int) -> DjSetVersion | None:
        """Return the newest version for a set — MAX(id) wins."""
        stmt = (
            select(DjSetVersion)
            .where(DjSetVersion.set_id == set_id)
            .order_by(DjSetVersion.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    async def count_for_set(self, set_id: int) -> int:
        """Return the number of versions for a set."""
        stmt = select(func.count()).select_from(DjSetVersion).where(DjSetVersion.set_id == set_id)
        return int(await self.session.scalar(stmt) or 0)

    async def get_render_inputs(self, version_id: int) -> list[TrackInput]:
        """Ordered render inputs for a version: title/bpm/key/mix-in/LUFS/file.

        One batch query joining dj_set_items ⋈ tracks ⋈
        track_audio_features_computed ⋈ dj_library_items. Raises
        ValidationError when a track has no registered audio file (download
        first — mirrors the L5 finalization contract).
        """
        import re

        from app.models.audio_file import DjLibraryItem
        from app.models.set import DjSetItem
        from app.models.track import Track
        from app.models.track_features import TrackAudioFeaturesComputed

        stmt = (
            select(
                DjSetItem.track_id,
                DjSetItem.sort_index,
                DjSetItem.mix_in_point_ms,
                Track.title,
                TrackAudioFeaturesComputed.bpm,
                TrackAudioFeaturesComputed.key_code,
                TrackAudioFeaturesComputed.integrated_lufs,
                DjLibraryItem.file_path,
            )
            .join(Track, Track.id == DjSetItem.track_id)
            .join(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == DjSetItem.track_id,
                isouter=True,
            )
            .join(DjLibraryItem, DjLibraryItem.track_id == DjSetItem.track_id, isouter=True)
            .where(DjSetItem.version_id == version_id)
            .order_by(DjSetItem.sort_index)
        )
        result = await self.session.execute(stmt)
        out: list[TrackInput] = []
        for row in result.all():
            if row.file_path is None:
                raise ValidationError(
                    f"audio_file not found for track {row.track_id} in version "
                    f"{version_id} — download first via "
                    "entity_create(entity='audio_file', data={'track_ids': [...]})"
                )
            if row.bpm is None:
                raise ValidationError(
                    f"track {row.track_id} has no bpm feature — analyze first (level>=2)"
                )
            m = re.search(r"\[(\d+)\]", row.file_path)
            yandex_id = int(m.group(1)) if m else None
            out.append(
                TrackInput(
                    track_id=row.track_id,
                    yandex_id=yandex_id,
                    title=row.title,
                    bpm=float(row.bpm),
                    key_code=row.key_code,
                    mix_in_ms=int(row.mix_in_point_ms or 0),
                    integrated_lufs=row.integrated_lufs,
                    file_path=row.file_path,
                )
            )
        return out

    # Alias matching the older name used by some resources.
    latest_version = get_latest
