"""Track repository — inherits BaseRepository CRUD + 4 domain methods."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, exists, select

from app.models.playlist import DjPlaylistItem
from app.models.track import Track, TrackExternalId
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.base import BaseRepository
from app.shared.errors import ValidationError
from app.shared.filters import parse_filter, split_lookup
from app.shared.pagination import Page

_TRACK_FEATURE_FILTER_FIELDS = frozenset({"bpm", "key_code", "mood"})
_TRACK_FEATURE_SORT_FIELDS = frozenset({"bpm", "key_code", "mood"})


class TrackRepository(BaseRepository[Track]):
    model = Track

    async def filter(
        self,
        *,
        where: dict[str, Any] | None = None,
        order: Sequence[str] | None = None,
        limit: int = 50,
        cursor: str | None = None,
        with_total: bool = False,
    ) -> Page[Track]:
        """Extends BaseRepository.filter with cross-table magic filters.

        ``has_features`` and ``playlist_id`` live on the ``track`` filter
        schema but are NOT columns on ``tracks``. Translate them into
        EXISTS clauses and let the base class handle every other lookup.
        ``None`` means "no constraint" — fall through.
        """
        where = dict(where or {})
        extras = []
        feature_where = self._pop_feature_filters(where)

        # ``normalize_bare_fields`` from entity_list converts the bare
        # ``has_features`` key to ``has_features__eq``; accept either form.
        flag = where.pop("has_features__eq", None)
        if flag is None:
            flag = where.pop("has_features", None)

        if flag is not None:
            features_exists = (
                exists()
                .where(TrackAudioFeaturesComputed.track_id == Track.id)
                .correlate(Track)
            )
            extras.append(features_exists if flag else ~features_exists)

        playlist_id = where.pop("playlist_id__eq", None)
        if playlist_id is None:
            playlist_id = where.pop("playlist_id", None)

        if playlist_id is not None:
            extras.append(
                exists().where(
                    and_(
                        DjPlaylistItem.track_id == Track.id,
                        DjPlaylistItem.playlist_id == playlist_id,
                    )
                ).correlate(Track)
            )

        if feature_where:
            extras.append(
                exists().where(
                    and_(
                        TrackAudioFeaturesComputed.track_id == Track.id,
                        *parse_filter(TrackAudioFeaturesComputed, feature_where),
                    )
                ).correlate(Track)
            )

        if extras or self._has_feature_order(order):
            return await self._filter_with_extra(
                and_(*extras) if extras else None,
                where=where,
                order=order,
                limit=limit,
                cursor=cursor,
                with_total=with_total,
            )

        return await super().filter(
            where=where, order=order, limit=limit, cursor=cursor, with_total=with_total
        )

    @staticmethod
    def _pop_feature_filters(where: dict[str, Any]) -> dict[str, Any]:
        feature_where: dict[str, Any] = {}
        for key in list(where):
            field, _ = split_lookup(key)
            if field in _TRACK_FEATURE_FILTER_FIELDS:
                feature_where[key] = where.pop(key)
        return feature_where

    @staticmethod
    def _has_feature_order(order: Sequence[str] | None) -> bool:
        for spec in order or ():
            field = spec.removesuffix("_desc").removesuffix("_asc")
            if field in _TRACK_FEATURE_SORT_FIELDS:
                return True
        return False

    @staticmethod
    def _order_column(field: str) -> Any:
        if field in _TRACK_FEATURE_SORT_FIELDS:
            return getattr(TrackAudioFeaturesComputed, field)
        column = getattr(Track, field, None)
        if column is None:
            raise ValidationError(f"unknown order field {field!r}")
        return column

    async def _filter_with_extra(
        self,
        extra: Any | None,
        *,
        where: dict[str, Any] | None,
        order: Sequence[str] | None,
        limit: int,
        cursor: str | None,
        with_total: bool,
    ) -> Page[Track]:
        """``BaseRepository.filter`` re-implementation that adds an extra clause.

        We can't override only the SELECT in the base class (it builds the
        statement monolithically), so we rebuild here while sharing all the
        keyset / order / cursor logic via the same helpers the base uses.
        """
        from app.shared.pagination import decode_cursor, encode_cursor

        order_clauses = list(order) if order else ["id"]
        needs_feature_join = self._has_feature_order(order_clauses)

        stmt = select(Track)
        if needs_feature_join:
            stmt = stmt.outerjoin(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == Track.id,
            )
        if extra is not None:
            stmt = stmt.where(extra)
        for clause in parse_filter(Track, where or {}):
            stmt = stmt.where(clause)

        if cursor is not None:
            cursor_id = decode_cursor(cursor)
            first_field = order_clauses[0].removesuffix("_desc").removesuffix("_asc")
            if first_field in _TRACK_FEATURE_SORT_FIELDS:
                raise ValidationError(
                    "cursor pagination is not supported when sorting track by "
                    f"feature field {first_field!r}; sort by 'id' for pagination"
                )
            column = self._order_column(first_field)
            stmt = (
                stmt.where(column < cursor_id)
                if order_clauses[0].endswith("_desc")
                else stmt.where(column > cursor_id)
            )

        for spec in order_clauses:
            if spec.endswith("_desc"):
                field, direction = spec.removesuffix("_desc"), "desc"
            elif spec.endswith("_asc"):
                field, direction = spec.removesuffix("_asc"), "asc"
            else:
                field, direction = spec, "asc"
            column = self._order_column(field)
            stmt = stmt.order_by(column.desc() if direction == "desc" else column.asc())

        stmt = stmt.limit(limit + 1)
        rows = list((await self.session.execute(stmt)).scalars().all())
        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor: str | None = None
        if has_more and items:
            first_field = order_clauses[0].removesuffix("_desc").removesuffix("_asc")
            if first_field not in _TRACK_FEATURE_SORT_FIELDS:
                next_cursor = encode_cursor(int(getattr(items[-1], first_field)))

        total: int | None = None
        if with_total:
            from sqlalchemy import func

            count_stmt = select(func.count()).select_from(Track)
            if extra is not None:
                count_stmt = count_stmt.where(extra)
            for clause in parse_filter(Track, where or {}):
                count_stmt = count_stmt.where(clause)
            total = int((await self.session.execute(count_stmt)).scalar_one())

        return Page(items=items, next_cursor=next_cursor, total=total)

    async def get_provider_id(self, track_id: int, platform: str) -> str | None:
        """Return ``external_id`` for ``track_id`` on ``platform`` or None."""
        stmt = select(TrackExternalId.external_id).where(
            TrackExternalId.track_id == track_id,
            TrackExternalId.platform == platform,
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    async def get_primary_artist_name(self, track_id: int) -> str | None:
        """Return the display artist name for ``track_id`` or None.

        Resolution order:

        1. ``role='primary'`` row (current import convention).
        2. Lowest ``artist_id`` among any role — covers older imports
           that tagged every artist with ``role='artist'``.

        Audit O-1: ``local://tracks/{id}.primary_artist_name`` was always
        null because ``TrackView.from_attributes`` looked for an
        attribute that ``Track`` doesn't expose. The resource now calls
        this method explicitly.
        """
        from app.models.track import Artist, TrackArtist

        primary = (
            select(Artist.name)
            .join(TrackArtist, TrackArtist.artist_id == Artist.id)
            .where(
                TrackArtist.track_id == track_id,
                TrackArtist.role == "primary",
            )
            .limit(1)
        )
        name = await self.session.scalar(primary)
        if name is not None:
            return str(name)
        any_role = (
            select(Artist.name)
            .join(TrackArtist, TrackArtist.artist_id == Artist.id)
            .where(TrackArtist.track_id == track_id)
            .order_by(TrackArtist.artist_id)
            .limit(1)
        )
        fallback = await self.session.scalar(any_role)
        return str(fallback) if fallback is not None else None

    async def get_primary_artist_names(self, track_ids: Sequence[int]) -> dict[int, str | None]:
        """Return display artist names for many tracks in one query.

        Mirrors ``get_primary_artist_name`` resolution order while avoiding
        the N+1 query pattern in list responses.
        """
        ids = list(dict.fromkeys(int(tid) for tid in track_ids))
        if not ids:
            return {}

        from app.models.track import Artist, TrackArtist

        stmt = (
            select(TrackArtist.track_id, Artist.name)
            .join(Artist, TrackArtist.artist_id == Artist.id)
            .where(TrackArtist.track_id.in_(ids))
            .order_by(
                TrackArtist.track_id,
                (TrackArtist.role != "primary").asc(),
                TrackArtist.artist_id,
            )
        )
        names: dict[int, str | None] = {tid: None for tid in ids}
        for track_id, name in (await self.session.execute(stmt)).all():
            if names.get(int(track_id)) is None:
                names[int(track_id)] = str(name)
        return names

    async def get_artists(self, track_id: int) -> list[Any]:
        """All artist credits for ``track_id`` as (artist_id, name, role) rows.

        Primary role sorts first, then lowest ``artist_id`` — mirrors the
        resolution order of ``get_primary_artist_name``. Backs
        ``entity_get(track, id, include_relations=["artists"])``.
        """
        from app.models.track import Artist, TrackArtist

        stmt = (
            select(
                Artist.id.label("artist_id"),
                Artist.name,
                TrackArtist.role,
            )
            .join(TrackArtist, TrackArtist.artist_id == Artist.id)
            .where(TrackArtist.track_id == track_id)
            .order_by((TrackArtist.role != "primary").asc(), TrackArtist.artist_id)
        )
        return list((await self.session.execute(stmt)).all())

    async def get_many(self, track_ids: list[int]) -> dict[int, Track]:
        """Batch-fetch tracks by primary keys. Returns ``{id: Track}``.

        Avoids the N+1 pattern of ``await uow.tracks.get(tid)`` inside a
        per-track loop. Missing IDs are simply absent from the result.
        """
        if not track_ids:
            return {}
        stmt = select(Track).where(Track.id.in_(track_ids))
        rows = (await self.session.execute(stmt)).scalars().all()
        return {t.id: t for t in rows}

    async def batch_get_by_provider_ids(
        self, platform: str, external_ids: list[str]
    ) -> dict[str, Track]:
        """Resolve many ``external_id`` values → Track instances in one query."""
        if not external_ids:
            return {}
        stmt = (
            select(TrackExternalId.external_id, Track)
            .join(Track, Track.id == TrackExternalId.track_id)
            .where(
                TrackExternalId.platform == platform,
                TrackExternalId.external_id.in_(external_ids),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return {ext_id: track for ext_id, track in rows}

    async def get_unanalyzed(self, level: int, limit: int = 100) -> list[int]:
        """Return track IDs whose analysis_level < ``level`` (or no features row)."""
        stmt = (
            select(Track.id)
            .outerjoin(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == Track.id,
            )
            .where(
                (TrackAudioFeaturesComputed.track_id.is_(None))
                | (TrackAudioFeaturesComputed.analysis_level < level)
            )
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def search_by_bpm_range(
        self,
        *,
        bpm_min: float,
        bpm_max: float,
        exclude_ids: set[int] | frozenset[int] | None = None,
        limit: int = 10,
    ) -> list[Track]:
        """Tracks whose latest features row sits within ``[bpm_min, bpm_max]``.

        Audit iter 37 (T-35): ``local://tracks/{id}/suggest_replacement``
        wanted this method via ``getattr(uow.tracks, "search_by_bpm_range",
        None)``; absent since v1.0 it always returned the placeholder
        reason "tracks repository does not expose search_by_bpm_range
        yet" — i.e. the replacement-candidate path never produced
        anything.

        Joined to ``track_audio_features_computed`` (INNER JOIN — tracks
        without features can't pass a BPM gate anyway). ``status=0``
        active filter is applied so archived/dead tracks are not offered
        as replacements. Excluded IDs are removed via NOT IN.
        """
        stmt = (
            select(Track)
            .join(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == Track.id,
            )
            .where(
                TrackAudioFeaturesComputed.bpm.is_not(None),
                TrackAudioFeaturesComputed.bpm >= bpm_min,
                TrackAudioFeaturesComputed.bpm <= bpm_max,
                Track.status == 0,
            )
            .order_by(Track.id.asc())
            .limit(limit)
        )
        if exclude_ids:
            stmt = stmt.where(Track.id.notin_(exclude_ids))
        return list((await self.session.execute(stmt)).scalars().all())

    async def ensure_external_id(
        self, track_id: int, platform: str, external_id: str
    ) -> TrackExternalId:
        """Upsert one (track_id, platform, external_id) mapping."""
        existing = await self.session.scalar(
            select(TrackExternalId).where(
                TrackExternalId.track_id == track_id,
                TrackExternalId.platform == platform,
            )
        )
        if existing is not None:
            if existing.external_id != external_id:
                existing.external_id = external_id
                await self.session.flush()
            return existing
        row = TrackExternalId(track_id=track_id, platform=platform, external_id=external_id)
        self.session.add(row)
        await self.session.flush()
        return row
