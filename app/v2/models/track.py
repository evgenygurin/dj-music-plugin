"""Track aggregate: Track + Artist + Genre + Release + 4 join tables + external IDs.

Port of legacy ``app/db/models/track.py`` + external-IDs slice of
``app/db/models/ingestion.py``. ``track_labels`` / ``labels`` dropped per
blueprint §13.2.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.v2.models.base import Base, TimestampMixin


class Track(Base, TimestampMixin):
    __tablename__ = "tracks"
    __table_args__ = (CheckConstraint("status IN (0, 1)", name="ck_track_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    sort_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[int] = mapped_column(default=0, server_default="0", index=True)

    track_artists: Mapped[list[TrackArtist]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    track_genres: Mapped[list[TrackGenre]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    track_releases: Mapped[list[TrackRelease]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    external_ids: Mapped[list[TrackExternalId]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )


class Artist(Base, TimestampMixin):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), unique=True)
    sort_name: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Genre(Base, TimestampMixin):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("genres.id", ondelete="SET NULL"), nullable=True, index=True
    )


class Release(Base, TimestampMixin):
    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    release_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    release_date: Mapped[date | None] = mapped_column(nullable=True)


class TrackArtist(Base):
    __tablename__ = "track_artists"
    __table_args__ = (
        UniqueConstraint("track_id", "artist_id", "role", name="uq_track_artist_role"),
    )

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), primary_key=True)

    track: Mapped[Track] = relationship(back_populates="track_artists")


class TrackGenre(Base):
    __tablename__ = "track_genres"

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[int] = mapped_column(
        ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )

    track: Mapped[Track] = relationship(back_populates="track_genres")


class TrackRelease(Base):
    __tablename__ = "track_releases"

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    release_id: Mapped[int] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True
    )
    track_number: Mapped[int | None] = mapped_column(nullable=True)

    track: Mapped[Track] = relationship(back_populates="track_releases")


class TrackExternalId(Base, TimestampMixin):
    __tablename__ = "track_external_ids"
    __table_args__ = (
        UniqueConstraint("provider_code", "external_id", name="uq_provider_external_id"),
        UniqueConstraint("track_id", "provider_code", name="uq_track_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    provider_code: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(200), index=True)

    track: Mapped[Track] = relationship(back_populates="external_ids")
