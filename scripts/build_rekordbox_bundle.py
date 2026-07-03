#!/usr/bin/env python3
"""One-command rekordbox bundle builder.

Flow:
1. Build import XML from a local folder of audio files.
2. Optionally copy audio files to a staging folder (for example on the USB drive).
3. If the USB rekordbox DB already contains matching tracks, also build a rich XML
   with beatgrid / cues / loops / load markers from the USB analysis data.
4. If the USB DB does not contain the tracks yet, stop with a precise message.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from export_folder_to_rekordbox_xml import export_folder
from export_usb_bundle_to_rekordbox_xml import export_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder with source audio files")
    parser.add_argument(
        "--usb-stage",
        type=Path,
        default=Path("/Volumes/USB DISK/Contents/TOP10_QUALITY"),
        help="Where to copy audio files before rekordbox import",
    )
    parser.add_argument(
        "--import-xml",
        type=Path,
        default=Path("generated-sets/TOP10_QUALITY/rekordbox.import.xml"),
        help="Path for the initial rekordbox XML import file",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("generated-sets/TOP10_QUALITY/rekordbox.bundle.json"),
        help="Path for the generated manifest",
    )
    parser.add_argument(
        "--rich-xml",
        type=Path,
        default=Path("generated-sets/TOP10_QUALITY/rekordbox.rich.xml"),
        help="Path for the rich XML rebuilt from USB analysis data",
    )
    parser.add_argument(
        "--playlist-name",
        default="TOP10 QUALITY",
        help="Playlist name inside rekordbox XML",
    )
    parser.add_argument(
        "--db",
        default="/Volumes/USB DISK/PIONEER/rekordbox/exportLibrary.db",
        help="Path to the USB exportLibrary.db",
    )
    parser.add_argument(
        "--volume-root",
        default="/Volumes/USB DISK",
        help="Mounted USB root",
    )
    parser.add_argument(
        "--allow-missing-rich",
        action="store_true",
        help="Do not fail if rich XML cannot be built yet",
    )
    return parser.parse_args()


def build_bundle(args: argparse.Namespace) -> dict[str, Any]:
    folder = args.folder.resolve()
    import_xml = args.import_xml.resolve()
    manifest = args.manifest.resolve()
    rich_xml = args.rich_xml.resolve()
    usb_stage = args.usb_stage.resolve()

    import_result = export_folder(
        folder=folder,
        output=import_xml,
        playlist_name=args.playlist_name,
        copy_to=usb_stage,
        manifest_output=manifest,
    )

    rich_result = export_bundle(
        manifest_path=manifest,
        db_path=args.db,
        volume_root=args.volume_root,
        output=rich_xml,
    )

    result = {
        "import": import_result,
        "rich": rich_result,
    }

    if rich_result["matched_tracks"] == 0 and not args.allow_missing_rich:
        raise SystemExit(
            json.dumps(
                {
                    "status": "needs_rekordbox_export",
                    "message": (
                        "Initial import bundle created, but the USB rekordbox database still "
                        "does not contain these tracks. Import the generated import XML into "
                        "rekordbox, analyze the tracks, export them to this USB, then rerun "
                        "the same command."
                    ),
                    "import_xml": import_result["output"],
                    "manifest": import_result["manifest"],
                    "usb_stage": str(usb_stage),
                    "rich_xml": str(rich_xml),
                    "unmatched_tracks": rich_result["unmatched"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return result


def main() -> None:
    args = parse_args()
    result = build_bundle(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
