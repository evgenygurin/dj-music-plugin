#!/usr/bin/env python3
"""Smoke-test pyrekordbox write access for OneLibrary exportLibrary.db.

Default mode is safe: copy the database and its WAL/SHM companions to a temp
directory, write a single memory cue there, reopen, and verify persistence.

Usage:
    .venv/bin/python scripts/test_pyrekordbox_onelibrary_write.py
    .venv/bin/python scripts/test_pyrekordbox_onelibrary_write.py --live
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import cast

from pyrekordbox import DeviceLibraryPlus
from pyrekordbox.devicelib_plus import models

DEFAULT_DB_PATH = Path("/Volumes/USB DISK/PIONEER/rekordbox/exportLibrary.db")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to OneLibrary exportLibrary.db",
    )
    parser.add_argument(
        "--track-id",
        type=int,
        default=None,
        help="Content ID to attach the test cue(s) to",
    )
    parser.add_argument(
        "--track-title",
        default=None,
        help="Exact track title to resolve to a content ID",
    )
    parser.add_argument(
        "--offset-ms",
        type=int,
        default=12345,
        help="Cue position in milliseconds",
    )
    parser.add_argument(
        "--label",
        default="pyrekordbox smoke test",
        help="Cue comment for the inserted test cue",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Write directly to the provided DB instead of a temporary copy",
    )
    parser.add_argument(
        "--profile",
        choices=("smoke", "all-cues", "exhaustive"),
        default="smoke",
        help="Write a single cue or a broad cue/hotcue/loop test set",
    )
    return parser.parse_args()


def copy_db_bundle(db_path: Path) -> tuple[Path, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="pyrekordbox-onelibrary-"))
    copied_db = temp_dir / db_path.name
    for suffix in ("", "-wal", "-shm"):
        source = Path(f"{db_path}{suffix}")
        if source.exists():
            shutil.copy2(source, Path(f"{copied_db}{suffix}"))
    return copied_db, temp_dir


def resolve_track_id(db: DeviceLibraryPlus, track_id: int | None, track_title: str | None) -> int:
    if track_id is not None:
        content = db.get_content(id=track_id)
        if content is None:
            raise SystemExit(f"track_id={track_id} not found")
        return cast(int, content.content_id)

    if not track_title:
        raise SystemExit("Either --track-id or --track-title is required")

    matches = db.query(models.Content).filter_by(title=track_title).all()
    if not matches:
        raise SystemExit(f"Track title not found: {track_title}")
    if len(matches) > 1:
        raise SystemExit(f"Track title is ambiguous: {track_title} ({len(matches)} matches)")
    return cast(int, matches[0].content_id)


def build_cues(profile: str, offset_ms: int, label: str, track_id: int) -> list[models.Cue]:
    def cue(
        *,
        kind: int,
        comment: str,
        in_ms: int,
        out_ms: int = 0,
        color: int = 0,
        active_loop: int = 0,
        loop_num: int = 0,
        loop_den: int = 0,
    ) -> models.Cue:
        return models.Cue(
            content_id=track_id,
            kind=kind,
            colorTableIndex=color,
            cueComment=comment,
            isActiveLoop=active_loop,
            beatLoopNumerator=loop_num,
            beatLoopDenominator=loop_den,
            inUsec=in_ms * 1000,
            outUsec=out_ms * 1000,
            in150FramePerSec=0,
            out150FramePerSec=0,
            inMpegFrameNumber=0,
            outMpegFrameNumber=0,
            inMpegAbs=0,
            outMpegAbs=0,
            inDecodingStartFramePosition=0,
            outDecodingStartFramePosition=0,
            inFileOffsetInBlock=0,
            outFileOffsetInBlock=0,
            inNumberOfSampleInBlock=0,
            outNumberOfSampleInBlock=0,
        )

    if profile == "smoke":
        return [
            cue(
                kind=0,
                comment=label,
                in_ms=offset_ms,
        )
    ]

    if profile == "exhaustive":
        cues = [
            cue(
                kind=0,
                comment=f"{label} memory cue base",
                in_ms=offset_ms,
                color=1,
            ),
            cue(
                kind=0,
                comment=f"{label} memory loop base",
                in_ms=offset_ms + 3000,
                out_ms=offset_ms + 15000,
                color=2,
                active_loop=1,
                loop_num=4,
                loop_den=1,
            ),
            cue(
                kind=3,
                comment=f"{label} load marker?",
                in_ms=offset_ms + 18000,
                color=3,
            ),
            cue(
                kind=4,
                comment=f"{label} loop kind 4",
                in_ms=offset_ms + 21000,
                out_ms=offset_ms + 33000,
                color=4,
                active_loop=1,
                loop_num=8,
                loop_den=1,
            ),
        ]
        for hotcue_button in range(1, 9):
            base_ms = offset_ms + 40000 + hotcue_button * 2500
            cues.append(
                cue(
                    kind=hotcue_button,
                    comment=f"{label} hot cue {hotcue_button} point",
                    in_ms=base_ms,
                    color=((hotcue_button - 1) % 8) + 1,
                )
            )
            cues.append(
                cue(
                    kind=hotcue_button,
                    comment=f"{label} hot cue {hotcue_button} loop",
                    in_ms=base_ms + 700,
                    out_ms=base_ms + 8700,
                    color=(hotcue_button % 8) + 1,
                    active_loop=1,
                    loop_num=hotcue_button if hotcue_button <= 8 else 8,
                    loop_den=1,
                )
            )
        return cues

    cues = [
        cue(
            kind=0,
            comment=f"{label} memory cue",
            in_ms=offset_ms,
            color=1,
        ),
        cue(
            kind=4,
            comment=f"{label} memory loop",
            in_ms=offset_ms + 4000,
            out_ms=offset_ms + 20000,
            color=2,
            active_loop=1,
            loop_num=4,
            loop_den=1,
        ),
    ]
    for hotcue_button in range(1, 9):
        cues.append(
            cue(
                kind=hotcue_button,
                comment=f"{label} hot cue {hotcue_button}",
                in_ms=offset_ms + 30000 + hotcue_button * 1000,
                color=(hotcue_button % 8) + 1,
            )
        )
    cues.append(
        cue(
            kind=8,
            comment=f"{label} hot loop 8",
            in_ms=offset_ms + 50000,
            out_ms=offset_ms + 66000,
            color=7,
            active_loop=1,
            loop_num=8,
            loop_den=1,
        )
    )
    return cues


def insert_test_cue(
    db_path: Path,
    track_id: int | None,
    track_title: str | None,
    offset_ms: int,
    label: str,
    profile: str,
) -> dict[str, object]:
    with DeviceLibraryPlus(db_path) as db:
        resolved_track_id = resolve_track_id(db, track_id, track_title)
        content = db.get_content(id=resolved_track_id)
        if content is None:
            raise SystemExit(f"track_id={resolved_track_id} not found in {db_path}")

        cue_count_before = db.get_cue(content_id=resolved_track_id).count()
        previous_update_count = content.cueUpdateCount

        cues = build_cues(profile, offset_ms, label, resolved_track_id)
        inserted_cue_ids: list[int] = []
        for cue in cues:
            db.add(cue)
        content.cueUpdateCount = (content.cueUpdateCount or 0) + len(cues)
        content.hasModified = 1
        db.flush()
        for cue in cues:
            inserted_cue_ids.append(cast(int, cue.cue_id))
        db.commit()

    with DeviceLibraryPlus(db_path) as verify_db:
        cue_count_after = verify_db.get_cue(content_id=resolved_track_id).count()
        inserted = [verify_db.get_cue(id=cue_id) for cue_id in inserted_cue_ids]
        content_after = verify_db.get_content(id=resolved_track_id)
        if any(cue is None for cue in inserted) or content_after is None:
            raise SystemExit("Inserted cue(s) could not be read back after commit")

    inserted_non_null = [cast(models.Cue, cue) for cue in inserted]

    return {
        "track_id": resolved_track_id,
        "cue_count_before": cue_count_before,
        "cue_count_after": cue_count_after,
        "inserted_count": len(inserted_non_null),
        "inserted_cues": [
            {
                "cue_id": cue.cue_id,
                "kind": cue.kind,
                "comment": cue.cueComment,
                "in_usec": cue.inUsec,
                "out_usec": cue.outUsec,
                "active_loop": cue.isActiveLoop,
                "color": cue.colorTableIndex,
                "loop_num": cue.beatLoopNumerator,
                "loop_den": cue.beatLoopDenominator,
            }
            for cue in inserted_non_null
        ],
        "content_title": content_after.title,
        "cue_update_count_before": previous_update_count,
        "cue_update_count_after": content_after.cueUpdateCount,
        "profile": profile,
    }


def main() -> None:
    args = parse_args()
    if not args.db_path.exists():
        raise SystemExit(f"DB not found: {args.db_path}")

    target_db = args.db_path
    temp_dir: Path | None = None
    mode = "live"
    if not args.live:
        target_db, temp_dir = copy_db_bundle(args.db_path)
        mode = "copy"

    result = insert_test_cue(
        db_path=target_db,
        track_id=args.track_id,
        track_title=args.track_title,
        offset_ms=args.offset_ms,
        label=args.label,
        profile=args.profile,
    )
    result["mode"] = mode
    result["source_db"] = str(args.db_path)
    result["tested_db"] = str(target_db)
    if temp_dir is not None:
        result["temp_dir"] = str(temp_dir)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
