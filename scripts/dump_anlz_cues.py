#!/usr/bin/env python3
"""Dump cue-related tags from Rekordbox ANLZ files (.DAT/.EXT/.2EX).

Tries the library parser first. If that fails or if raw output is requested, it
falls back to a tolerant binary parser for `PCOB`/`PCO2`.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

from pyrekordbox import AnlzFile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to ANLZ0000.DAT/.EXT/.2EX")
    parser.add_argument("--raw", action="store_true", help="Use tolerant raw parser only")
    return parser.parse_args()


def normalize(value: Any) -> Any:
    if hasattr(value, "items"):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def scan_tags(data: bytes) -> list[dict[str, Any]]:
    if data[:4] != b"PMAI":
        raise ValueError("Not an ANLZ PMAI file")
    len_header = struct.unpack(">I", data[4:8])[0]
    tags: list[dict[str, Any]] = []
    off = len_header
    while off + 12 <= len(data):
        tag = data[off : off + 4]
        if not all(32 <= b < 127 for b in tag):
            break
        len_tag_header = struct.unpack(">I", data[off + 4 : off + 8])[0]
        len_tag = struct.unpack(">I", data[off + 8 : off + 12])[0]
        if len_tag <= 0 or off + len_tag > len(data):
            break
        tags.append(
            {
                "offset": off,
                "tag": tag.decode("ascii"),
                "len_header": len_tag_header,
                "len_tag": len_tag,
            }
        )
        off += len_tag
    return tags


def parse_pcob(tag_data: bytes, offset: int) -> dict[str, Any]:
    cue_type, unk, count, memory_count = struct.unpack(">IHHI", tag_data[12:24])
    entries: list[dict[str, Any]] = []
    off = 24
    for _ in range(count):
        entry = tag_data[off : off + 56]
        entries.append(
            {
                "offset": offset + off,
                "tag": entry[:4].decode("ascii"),
                "len_header": struct.unpack(">I", entry[4:8])[0],
                "len_entry": struct.unpack(">I", entry[8:12])[0],
                "hot_cue": struct.unpack(">I", entry[12:16])[0],
                "status": struct.unpack(">I", entry[16:20])[0],
                "u1": struct.unpack(">I", entry[20:24])[0],
                "order_first": struct.unpack(">H", entry[24:26])[0],
                "order_last": struct.unpack(">H", entry[26:28])[0],
                "type": entry[28],
                "u2": struct.unpack(">H", entry[30:32])[0],
                "time_ms": struct.unpack(">I", entry[32:36])[0],
                "loop_time_ms": struct.unpack(">I", entry[36:40])[0],
            }
        )
        off += struct.unpack(">I", entry[8:12])[0]
    return {
        "offset": offset,
        "tag": "PCOB",
        "len_header": struct.unpack(">I", tag_data[4:8])[0],
        "len_tag": struct.unpack(">I", tag_data[8:12])[0],
        "cue_type": cue_type,
        "unk": unk,
        "count": count,
        "memory_count": memory_count,
        "entries": entries,
    }


def parse_pco2(tag_data: bytes, offset: int) -> dict[str, Any]:
    object_type, count, unknown = struct.unpack(">IHH", tag_data[12:20])
    entries: list[dict[str, Any]] = []
    off = 20
    for _ in range(count):
        if off + 12 > len(tag_data):
            break
        len_entry = struct.unpack(">I", tag_data[off + 8 : off + 12])[0]
        if len_entry <= 0 or off + len_entry > len(tag_data):
            break
        entry = tag_data[off : off + len_entry]
        len_entry = struct.unpack(">I", entry[8:12])[0]
        len_comment = struct.unpack(">I", entry[40:44])[0]
        comment_raw = entry[44 : 44 + len_comment]
        comment = comment_raw.decode("utf-16-be", errors="ignore").rstrip("\x00")
        color_index = 44 + len_comment
        color_tail = entry[color_index : color_index + 4]
        color_code, color_red, color_green, color_blue = (
            [*list(color_tail), 0, 0, 0, 0]
        )[:4]
        entries.append(
            {
                "offset": offset + off,
                "tag": entry[:4].decode("ascii"),
                "len_header": struct.unpack(">I", entry[4:8])[0],
                "len_entry": len_entry,
                "hot_cue": struct.unpack(">I", entry[12:16])[0],
                "type": entry[16],
                "u2": struct.unpack(">H", entry[18:20])[0],
                "time_ms": struct.unpack(">I", entry[20:24])[0],
                "loop_time_ms": struct.unpack(">I", entry[24:28])[0],
                "color_id": entry[28],
                "loop_numerator": struct.unpack(">H", entry[36:38])[0],
                "loop_denominator": struct.unpack(">H", entry[38:40])[0],
                "len_comment": len_comment,
                "comment": comment,
                "color_code": color_code,
                "color_red": color_red,
                "color_green": color_green,
                "color_blue": color_blue,
            }
        )
        off += len_entry
    return {
        "offset": offset,
        "tag": "PCO2",
        "len_header": struct.unpack(">I", tag_data[4:8])[0],
        "len_tag": struct.unpack(">I", tag_data[8:12])[0],
        "object_type": object_type,
        "count": count,
        "unknown": unknown,
        "entries": entries,
    }


def parse_pqtz(tag_data: bytes, offset: int) -> dict[str, Any]:
    entry_count = struct.unpack(">I", tag_data[20:24])[0]
    entries: list[dict[str, Any]] = []
    off = 24
    for _ in range(entry_count):
        if off + 8 > len(tag_data):
            break
        beat, tempo, time_ms = struct.unpack(">HHI", tag_data[off : off + 8])
        entries.append(
            {
                "offset": offset + off,
                "beat": beat,
                "tempo_x100": tempo,
                "bpm": tempo / 100,
                "time_ms": time_ms,
            }
        )
        off += 8
    return {
        "offset": offset,
        "tag": "PQTZ",
        "len_header": struct.unpack(">I", tag_data[4:8])[0],
        "len_tag": struct.unpack(">I", tag_data[8:12])[0],
        "entry_count": entry_count,
        "entries": entries,
    }


def raw_dump(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    tags = scan_tags(data)
    payload: dict[str, Any] = {
        "path": str(path),
        "raw_tags": tags,
        "PCOB": [],
        "PCO2": [],
        "PQTZ": [],
    }
    for tag in tags:
        off = tag["offset"]
        tag_data = data[off : off + tag["len_tag"]]
        if tag["tag"] == "PCOB":
            payload["PCOB"].append(parse_pcob(tag_data, off))
        elif tag["tag"] == "PCO2":
            payload["PCO2"].append(parse_pco2(tag_data, off))
        elif tag["tag"] == "PQTZ":
            payload["PQTZ"].append(parse_pqtz(tag_data, off))
    return payload


def main() -> None:
    args = parse_args()
    if args.raw:
        payload = raw_dump(args.path)
    else:
        try:
            anlz = AnlzFile.parse_file(args.path)
            payload = {
                "path": str(args.path),
                "tag_types": anlz.tag_types,
            }
            for key in ("PCOB", "PCO2"):
                if key in anlz:
                    payload[key] = [normalize(tag.get()) for tag in anlz.getall_tags(key)]
        except Exception as exc:
            payload = raw_dump(args.path)
            payload["parser_error"] = repr(exc)

    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
