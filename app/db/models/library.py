"""DJ library models — file items, beatgrids, cues, loops (REQUIREMENTS §2.3)."""

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class DjLibraryItem(Base, TimestampMixin):
    """A physical audio file in the DJ library."""

    __tablename__ = "dj_library_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    file_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_hash: Mapped[str] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column()
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bitrate: Mapped[int | None] = mapped_column(nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(nullable=True)
    channels: Mapped[int | None] = mapped_column(nullable=True)
    source_app: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # relationships
    beatgrids: Mapped[list["DjBeatgrid"]] = relationship(
        back_populates="library_item", cascade="all, delete-orphan"
    )
    cue_points: Mapped[list["DjCuePoint"]] = relationship(
        back_populates="library_item", cascade="all, delete-orphan"
    )
    saved_loops: Mapped[list["DjSavedLoop"]] = relationship(
        back_populates="library_item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"DjLibraryItem(id={self.id}, track_id={self.track_id}, path={self.file_path!r})"


class DjBeatgrid(Base, TimestampMixin):
    """BPM grid for a track."""

    __tablename__ = "dj_beatgrids"

    id: Mapped[int] = mapped_column(primary_key=True)
    library_item_id: Mapped[int] = mapped_column(
        ForeignKey("dj_library_items.id", ondelete="CASCADE"), index=True
    )
    bpm: Mapped[float] = mapped_column()
    first_downbeat_ms: Mapped[float | None] = mapped_column(nullable=True)
    grid_offset_ms: Mapped[float | None] = mapped_column(nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    variable_tempo: Mapped[bool] = mapped_column(default=False, server_default="false")
    canonical: Mapped[bool] = mapped_column(default=False, server_default="false")

    # relationships
    library_item: Mapped["DjLibraryItem"] = relationship(back_populates="beatgrids")
    change_points: Mapped[list["DjBeatgridChangePoint"]] = relationship(
        back_populates="beatgrid", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("bpm >= 20 AND bpm <= 300", name="ck_bg_bpm"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_bg_confidence",
        ),
    )

    def __repr__(self) -> str:
        return f"DjBeatgrid(id={self.id}, bpm={self.bpm}, canonical={self.canonical})"


class DjBeatgridChangePoint(Base):
    """Variable BPM change point within a beatgrid."""

    __tablename__ = "dj_beatgrid_change_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    beatgrid_id: Mapped[int] = mapped_column(
        ForeignKey("dj_beatgrids.id", ondelete="CASCADE"), index=True
    )
    position_ms: Mapped[float] = mapped_column()
    bpm: Mapped[float] = mapped_column()

    # relationships
    beatgrid: Mapped["DjBeatgrid"] = relationship(back_populates="change_points")

    __table_args__ = (CheckConstraint("bpm >= 20 AND bpm <= 300", name="ck_bgcp_bpm"),)

    def __repr__(self) -> str:
        return f"DjBeatgridChangePoint(id={self.id}, pos={self.position_ms}ms, bpm={self.bpm})"


class DjCuePoint(Base, TimestampMixin):
    """A named position (cue/hot cue) in a track."""

    __tablename__ = "dj_cue_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    library_item_id: Mapped[int] = mapped_column(
        ForeignKey("dj_library_items.id", ondelete="CASCADE"), index=True
    )
    position_ms: Mapped[float] = mapped_column()
    kind: Mapped[int] = mapped_column()
    hotcue_index: Mapped[int | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantized: Mapped[bool] = mapped_column(default=False, server_default="false")
    source_app: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # relationships
    library_item: Mapped["DjLibraryItem"] = relationship(back_populates="cue_points")

    __table_args__ = (
        CheckConstraint("kind >= 0 AND kind <= 7", name="ck_cue_kind"),
        CheckConstraint(
            "hotcue_index IS NULL OR (hotcue_index >= 0 AND hotcue_index <= 15)",
            name="ck_cue_hotcue_index",
        ),
    )

    def __repr__(self) -> str:
        return f"DjCuePoint(id={self.id}, pos={self.position_ms}ms, kind={self.kind})"


class DjSavedLoop(Base, TimestampMixin):
    """A saved loop region in a track."""

    __tablename__ = "dj_saved_loops"

    id: Mapped[int] = mapped_column(primary_key=True)
    library_item_id: Mapped[int] = mapped_column(
        ForeignKey("dj_library_items.id", ondelete="CASCADE"), index=True
    )
    in_position_ms: Mapped[float] = mapped_column()
    out_position_ms: Mapped[float] = mapped_column()
    length_ms: Mapped[float | None] = mapped_column(nullable=True)
    hotcue_index: Mapped[int | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    active_on_load: Mapped[bool] = mapped_column(default=False, server_default="false")
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_app: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # relationships
    library_item: Mapped["DjLibraryItem"] = relationship(back_populates="saved_loops")

    __table_args__ = (
        CheckConstraint(
            "hotcue_index IS NULL OR (hotcue_index >= 0 AND hotcue_index <= 15)",
            name="ck_loop_hotcue_index",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"DjSavedLoop(id={self.id}, in={self.in_position_ms}ms, out={self.out_position_ms}ms)"
        )
