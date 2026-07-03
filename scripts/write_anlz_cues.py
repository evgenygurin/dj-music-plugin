#!/usr/bin/env python3
"""Write cue markers into Rekordbox ANLZ0000.DAT and ANLZ0000.EXT.

Builds PCPT / PCP2 entries byte-by-byte with the exact constants rekordbox
CDJ/XDJ hardware expects (verified to round-trip through pyrekordbox's
strict Construct parser):
  - status = 4          (enabled; djay writes 0 which only djay reads)
  - u1     = 0x10000    (65536)
  - u2     = 1000

rekordbox reads base cue positions from DAT (PCOB/PCPT) and extended
metadata (colors, comments) from EXT (PCO2/PCP2).  Both files must be
updated; in EXT, PCOB/PCO2 tags are placed before the trailing PQT2 tag.

===============================================================================
MARKER TYPES — WHAT THE FORMAT SUPPORTS (and what this writer implements)
===============================================================================

The ANLZ format (and the parallel `exportLibrary.db` Cue table) supports
several distinct marker types.  This writer currently **only implements hot
cue single points** (the case that was tested on real hardware).  The other
types are documented below so they can be implemented later.

The enum values come from pyrekordbox `anlz/structs.py`:

    AnlzTagCueObjectType (PCOB/PCO2 cue_type):
        memory = 0   # memory cue bank (separate PCOB tag)
        hotcue = 1   # hot cue bank (the one we tested)

    AnlzCuePointType (PCPT entry `type` byte):
        single = 1   # a point (cue or hot cue)  <-- IMPLEMENTED
        loop   = 2   # a loop region             <-- NOT IMPLEMENTED

    AnlzCuePointStatus (PCPT entry `status` u32):
        disabled = 0
        enabled  = 4   # always use this

--- 1. HOT CUES (IMPLEMENTED & HARDWARE-TESTED) -------------------------------

Hot cue pads 1-8.  Each is a single point with a color.

    PCPT entry (DAT, PCOB cue_type=hotcue):
        hot_cue  = 1..8      (pad number)
        type     = 1         (single)
        status   = 4         (enabled)
        time     = <ms>
        loop_time= -1        (no loop)
    PCP2 entry (EXT, PCO2 type=hotcue):
        hot_cue  = 1..8
        color_red/green/blue = <RGB>
        comment  = ""        (optional, UTF-16-BE)

Example JSON:
    [
        {"hot_cue": 1, "time_ms": 59031, "color": [255, 0, 69]},
        {"hot_cue": 2, "time_ms": 60973, "color": [255, 117, 0]}
    ]

--- 2. MEMORY CUES (NOT IMPLEMENTED — format understood) ----------------------

Memory cues are stored in a SEPARATE PCOB tag with cue_type=memory (0).
They appear as a list of points on the waveform (no color, no pad).
In DAT there are usually two PCOB tags: PCOB(memory, entries) and
PCOB(hotcue, entries).  djay writes them in that order.

To implement: add a second cue bank in write_cues_to_dat/write_cues_to_ext
that builds PCOB(cue_type=memory) with hot_cue=0 in each PCPT entry.

    PCPT entry (DAT, PCOB cue_type=memory):
        hot_cue  = 0         (memory cue marker, not a pad)
        type     = 1         (single)
        status   = 4
        time     = <ms>
        loop_time= -1
    (no PCP2 entry needed — memory cues have no color in EXT)

--- 3. LOOPS (NOT IMPLEMENTED — format understood) ----------------------------

A loop is a region (in-point + out-point).  In PCPT, `type=2` (loop) and
`loop_time` holds the out-point in ms.  In PCO2, `loop_enumerator`/
`loop_denominator` store the beat-loop size (e.g. 4/1 = 4-beat loop).
Active loops also set isActiveLoop=1 and beatLoopNumerator/Denominator in
the exportLibrary.db Cue row.

    PCPT entry (DAT):
        type      = 2        (loop)
        time      = <in_ms>
        loop_time = <out_ms> (NOT -1)
    PCP2 entry (EXT):
        loop_enumerator   = <beats>   (e.g. 4)
        loop_denominator  = 1
        comment           = "" (optional)
        color_red/green/blue = <RGB>

Hot-cue loops (a hot cue pad that activates a loop) use the same structure
but with hot_cue = 1..8.

To implement: extend build_pcpt_entry/build_pcp2_entry to accept
loop_time_ms and type=2, and route loop cues to a separate list.

--- 4. LOAD MARKER (NOT IMPLEMENTED — uncertain) ------------------------------

The exportLibrary.db Cue table has kind=3 ("Load").  In the ANLZ format
this may correspond to a special PCPT entry marking the default load
position.  Not reverse-engineered in detail — needs investigation.

--- 5. exportLibrary.db SYNC (NOT IMPLEMENTED — separate concern) -------------

For full rekordbox-software compatibility (not just CDJ hardware), the
`exportLibrary.db` Cue table should also be updated via pyrekordbox's
DeviceLibraryPlus ORM:

    from pyrekordbox import DeviceLibraryPlus
    from pyrekordbox.devicelib_plus.models import Cue
    db = DeviceLibraryPlus("exportLibrary.db")
    cue = Cue(content_id=..., kind=1, inUsec=time_ms*1000, ...)
    db.add(cue)
    content.cueUpdateCount = (content.cueUpdateCount or 0) + 1
    content.hasModified = 1
    db.commit()

CDJ/XDJ hardware reads cues from ANLZ files directly, so DB sync is only
needed for the rekordbox desktop application.  See
scripts/test_pyrekordbox_onelibrary_write.py for a DB-only write prototype.

===============================================================================
REFERENCE: pyrekordbox struct fields (anlz/structs.py)
===============================================================================

AnlzCuePoint (PCPT, 56 bytes total: 40 fields + 16 padding):
    type        Const("PCPT")
    len_header  28
    len_entry   56
    hot_cue     u32  (0 for memory, 1-8 for hot cue pad)
    status      u32  Enum: disabled=0, enabled=4
    u1          u32  Const 0x10000
    order_first u16  (0xffff for first cue)
    order_last  u16  (0xffff for last cue)
    type        u8   Enum: single=1, loop=2
    (1 byte padding)
    u2          u16  Const 1000
    time        u32  position in ms
    loop_time   i32  loop out-point in ms, -1 if not a loop
    (16 bytes padding)

AnlzCuePoint2 (PCP2, variable: 48 base + comment + padding):
    type              Const("PCP2")
    len_header        16
    len_entry         variable
    hot_cue           u32
    type              u8   (1=hot cue point)
    (3 bytes padding)
    time              u32
    loop_time         i32  -1 if not a loop
    color_id          u8   (0)
    (7 bytes padding)
    loop_enumerator   u16  (beats, for beat loops)
    loop_denominator  u16  (usually 1)
    len_comment       u32  (bytes of UTF-16-BE)
    comment           UTF-16-BE string
    color_code        u8   (0)
    color_red         u8
    color_green       u8
    color_blue        u8
    (padding to len_entry)

===============================================================================
Usage:
===============================================================================

    # Dry-run
    .venv/bin/python scripts/write_anlz_cues.py <ANLZ_DIR> dry-run --cues '<JSON>'

    # Write to both DAT + EXT (with backup)
    .venv/bin/python scripts/write_anlz_cues.py <ANLZ_DIR> write --cues '<JSON>'

    # Verify (read-back via raw parser)
    .venv/bin/python scripts/write_anlz_cues.py <ANLZ_DIR> verify

    Example JSON (all marker types supported):

    # Hot cue single points (HARDWARE-TESTED)
    [
        {"hot_cue": 1, "time_ms": 59031, "color": [255, 0, 69]},
        {"hot_cue": 2, "time_ms": 60973, "color": [255, 117, 0]}
    ]

    # Memory cue (point on waveform, no pad, no color)
    # Format-understood, NOT hardware-tested.
    [
        {"type": "memory", "time_ms": 30000}
    ]

    # Hot cue loop (pad activates a beat-loop)
    # Format-understood, NOT hardware-tested.
    [
        {"hot_cue": 3, "time_ms": 60000, "loop_time_ms": 66000,
         "loop_num": 4, "loop_den": 1, "color": [0, 255, 0]}
    ]

    # Mixed: memory + hot cues + loop
    [
        {"type": "memory", "time_ms": 10000},
        {"hot_cue": 1, "time_ms": 30000, "color": [255, 0, 69]},
        {"hot_cue": 2, "time_ms": 60000, "loop_time_ms": 66000,
         "loop_num": 4, "loop_den": 1, "color": [0, 255, 0]}
    ]

    # Start / End (load markers) — written to exportLibrary.db, not ANLZ
    [
        {"type": "start", "time_ms": 5000},
        {"type": "end", "time_ms": 380000}
    ]

Cue dict fields:
    type         "hotcue" (default), "memory", "start", or "end"
    hot_cue      1..8 for hot cue pads (ignored for memory/start/end cues)
    time_ms      in-point position in milliseconds (required)
    loop_time_ms out-point in ms; -1 or absent = single point, set = loop
    loop_num     beat-loop numerator   (e.g. 4 for a 4-beat loop)
    loop_den     beat-loop denominator (usually 1)
    color        [R, G, B] 0-255 (hot cues only; memory/start/end have no color)
    comment      optional UTF-16-BE string

--- 6. exportLibrary.db START/END MARKERS (IMPLEMENTED via write-db) ------

Start (load-in) and End (load-out) markers define the playable region of a
track.  CDJ reads these from the Cue table in exportLibrary.db (NOT from ANLZ).

    Cue row:  kind=3 ("load"), inUsec=<time_ms * 1000>

The first kind=3 row is treated as the START (load-in point), the second as
the END (load-out point).  If only one is set, the other defaults to track
beginning / end.

Usage:

    # Write cues to ANLZ (DAT + EXT) AND exportLibrary.db in one shot:
    .venv/bin/python scripts/write_anlz_cues.py <ANLZ_DIR> write-db --db <DB_PATH> --cues '<JSON>'
    # or just ANLZ (no --db flag):
    .venv/bin/python scripts/write_anlz_cues.py <ANLZ_DIR> write --cues '<JSON>'

The `write-db` command combines ANLZ write + DB Cue table update.
Pass --db to point at exportLibrary.db; the script finds the matching
content row by matching analysisDataFilePath against the ANLZ dir.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# PMAI / ANLZ tag scanning (tolerant, bypasses pyrekordbox strict parser)
# ---------------------------------------------------------------------------

def scan_pmai_tags(data: bytes) -> list[tuple[str, int, int]]:
    """Scan a PMAI file, return list of (tag_name, offset, len_tag)."""
    if data[:4] != b"PMAI":
        raise ValueError("Not an ANLZ PMAI file")
    header_len = struct.unpack(">I", data[4:8])[0]
    tags: list[tuple[str, int, int]] = []
    off = header_len
    while off + 12 <= len(data):
        tag_name_raw = data[off : off + 4]
        if not all(32 <= b < 127 for b in tag_name_raw):
            break
        tag_name = tag_name_raw.decode("ascii")
        len_tag = struct.unpack(">I", data[off + 8 : off + 12])[0]
        if len_tag <= 0 or off + len_tag > len(data):
            break
        tags.append((tag_name, off, len_tag))
        off += len_tag
    return tags


def strip_cue_tags(data: bytes) -> bytes:
    """Remove any existing PCOB / PCO2 tags, return remaining bytes."""
    header_len = struct.unpack(">I", data[4:8])[0]
    chunks: list[bytes] = [data[:header_len]]
    for tag_name, off, len_tag in scan_pmai_tags(data):
        if tag_name not in ("PCOB", "PCO2"):
            chunks.append(data[off : off + len_tag])
    return b"".join(chunks)


def fix_file_header_length(data: bytes) -> bytes:
    """Update PMAI header len_file to match actual data length."""
    return data[:8] + struct.pack(">I", len(data)) + data[12:]


# ---------------------------------------------------------------------------
# PCPT / PCP2 entry builders (byte-level, verified to round-trip pyrekordbox)
# ---------------------------------------------------------------------------

PCPT_ENTRY_SIZE = 56  # 40 bytes fields + 16 bytes 0xFF padding


def build_pcpt_entry(
    hot_cue: int,
    time_ms: int,
    loop_time_ms: int = -1,
    order_first: int = 0,
    order_last: int = 0,
    cue_type: int = 1,  # AnlzCuePointType: 1=single, 2=loop
) -> bytes:
    """Build a single PCPT entry (56 bytes) with rekordbox-expected constants.

    Supports:
      - Hot cue single points  (hot_cue=1..8, cue_type=1, loop_time_ms=-1)
        IMPLEMENTED & HARDWARE-TESTED.
      - Memory cues            (hot_cue=0,    cue_type=1, loop_time_ms=-1)
        Format-understood, NOT hardware-tested.
      - Loops                  (cue_type=2,   loop_time_ms=<out-point ms>)
        Format-understood, NOT hardware-tested.

    Layout (verified against pyrekordbox AnlzCuePoint struct):
        +0..3   tag 'PCPT'
        +4..7   len_header = 28
        +8..11  len_entry  = 56
        +12..15 hot_cue    (u32 BE)
        +16..19 status     (u32 BE) = 4 (enabled)
        +20..23 u1         (u32 BE) = 0x10000 (65536)
        +24..25 order_first (u16 BE)
        +26..27 order_last  (u16 BE)
        +28     cue_type   (u8) = 1 (single) or 2 (loop)
        +29     pad        (u8) = 0
        +30..31 u2         (u16 BE) = 1000
        +32..35 time_ms    (u32 BE)
        +36..39 loop_time  (i32 BE) = -1 if not a loop, else out-point in ms
        +40..55 padding    = 0xFF (16 bytes)
    """
    entry = bytearray(PCPT_ENTRY_SIZE)
    entry[0:4] = b"PCPT"
    struct.pack_into(">II", entry, 4, 28, 56)
    struct.pack_into(">I", entry, 12, hot_cue)
    struct.pack_into(">I", entry, 16, 4)          # status = enabled
    struct.pack_into(">I", entry, 20, 0x10000)    # u1 const
    struct.pack_into(">HH", entry, 24, order_first, order_last)
    entry[28] = cue_type
    entry[29] = 0
    struct.pack_into(">H", entry, 30, 1000)       # u2 const
    struct.pack_into(">I", entry, 32, time_ms)
    struct.pack_into(">i", entry, 36, loop_time_ms)
    for i in range(40, 56):
        entry[i] = 0xFF
    return bytes(entry)


def build_pcp2_entry(
    hot_cue: int,
    time_ms: int,
    color: tuple[int, int, int] = (255, 0, 69),
    loop_time_ms: int = -1,
    comment: str = "",
    cue_type: int = 1,
    loop_num: int = 0,
    loop_den: int = 0,
) -> bytes:
    """Build a single PCP2 entry (variable size, min 56 bytes).

    Layout (verified against pyrekordbox AnlzCuePoint2 struct):
        +0..3   tag 'PCP2'
        +4..7   len_header = 16
        +8..11  len_entry  (u32 BE)
        +12..15 hot_cue    (u32 BE)
        +16     cue_type   (u8) = 1
        +17..19 padding    (3 bytes)
        +20..23 time_ms    (u32 BE)
        +24..27 loop_time  (i32 BE) = -1 if no loop
        +28     color_id   (u8) = 0
        +29..35 padding    (7 bytes)
        +36..37 loop_enumerator (u16 BE)
        +38..39 loop_denominator (u16 BE)
        +40..43 len_comment (u32 BE) — bytes of UTF-16-BE
        +44..44+CL  comment data (UTF-16-BE)
        +44+CL   color_code (u8) = 0
        +45+CL   red   (u8)
        +46+CL   green (u8)
        +47+CL   blue  (u8)
        +48+CL.. padding to fill len_entry
    """
    comment_bytes = comment.encode("utf-16-be") if comment else b""
    comment_len = len(comment_bytes)

    # len_entry: 48 bytes fixed + comment_len + padding to align (we pad to 56 minimum)
    base = 48 + comment_len
    pad_to_56 = 56 - base if base < 56 else (4 - (base % 4)) % 4
    len_entry = base + pad_to_56

    entry = bytearray(len_entry)
    entry[0:4] = b"PCP2"
    struct.pack_into(">II", entry, 4, 16, len_entry)
    struct.pack_into(">I", entry, 12, hot_cue)
    entry[16] = cue_type
    struct.pack_into(">I", entry, 20, time_ms)
    struct.pack_into(">i", entry, 24, loop_time_ms)
    entry[28] = 0  # color_id
    struct.pack_into(">HH", entry, 36, loop_num, loop_den)
    struct.pack_into(">I", entry, 40, comment_len)
    if comment_bytes:
        entry[44 : 44 + comment_len] = comment_bytes
    color_off = 44 + comment_len
    entry[color_off] = 0              # color_code
    entry[color_off + 1] = color[0]   # red
    entry[color_off + 2] = color[1]   # green
    entry[color_off + 3] = color[2]   # blue
    # remaining bytes are already zero (padding)
    return bytes(entry)


# ---------------------------------------------------------------------------
# PCOB / PCO2 tag builders
# ---------------------------------------------------------------------------

# Marker type constants
CUE_SINGLE = 1   # AnlzCuePointType.single
CUE_LOOP = 2     # AnlzCuePointType.loop


def _is_loop(cue: dict[str, Any]) -> bool:
    """A cue is a loop if it has a loop_time_ms out-point (not -1)."""
    return cue.get("loop_time_ms", -1) != -1


def _pcpt_type_for(cue: dict[str, Any]) -> int:
    """Return AnlzCuePointType for a cue (1=single, 2=loop)."""
    return CUE_LOOP if _is_loop(cue) else CUE_SINGLE


def build_pcob_tag(cues: list[dict[str, Any]], cue_type: str = "hotcue") -> bytes:
    """Build a complete PCOB tag for one cue bank (memory or hotcue).

    Header (24 bytes):
        +0..3   tag 'PCOB'
        +4..7   len_header = 24
        +8..11  len_tag    (u32 BE)
        +12..15 cue_type   (u32 BE) = 1 (hotcue) or 0 (memory)
        +16..17 unk        (u16 BE) = 0
        +18..19 count      (u16 BE) = N
        +20..23 memory_count (i32 BE) = 0

    Each entry is built via build_pcpt_entry; loops get cue_type=2 and a
    loop_time out-point, single points get cue_type=1 and loop_time=-1.
    Hot-cue pads use hot_cue=1..8, memory cues use hot_cue=0.
    """
    cue_type_val = 1 if cue_type == "hotcue" else 0
    n = len(cues)
    entries_data = b"".join(
        build_pcpt_entry(
            hot_cue=c["hot_cue"],
            time_ms=c["time_ms"],
            loop_time_ms=c.get("loop_time_ms", -1),
            cue_type=_pcpt_type_for(c),
        )
        for c in cues
    )
    len_tag = 24 + len(entries_data)

    header = bytearray(24)
    header[0:4] = b"PCOB"
    struct.pack_into(">II", header, 4, 24, len_tag)
    struct.pack_into(">I", header, 12, cue_type_val)
    struct.pack_into(">H", header, 16, 0)       # unk
    struct.pack_into(">H", header, 18, n)       # count
    struct.pack_into(">i", header, 20, 0)       # memory_count

    return bytes(header) + entries_data


def build_pcob_empty(cue_type: str = "memory") -> bytes:
    """Build an empty PCOB tag (terminator used at end of DAT)."""
    cue_type_val = 1 if cue_type == "hotcue" else 0
    header = bytearray(24)
    header[0:4] = b"PCOB"
    struct.pack_into(">II", header, 4, 24, 24)  # len_tag = header only
    struct.pack_into(">I", header, 12, cue_type_val)
    struct.pack_into(">H", header, 16, 0)
    struct.pack_into(">H", header, 18, 0)
    struct.pack_into(">i", header, 20, 0)
    return bytes(header)


def build_pco2_tag(cues: list[dict[str, Any]], cue_type: str = "hotcue") -> bytes:
    """Build a complete PCO2 tag (extended cue list with colors/comments).

    Header (20 bytes):
        +0..3   tag 'PCO2'
        +4..7   len_header = 20
        +8..11  len_tag    (u32 BE)
        +12..15 type       (u32 BE) = 1 (hotcue) or 0 (memory)
        +16..17 count      (u16 BE) = N
        +18..19 unknown    (u16 BE) = 0

    Each PCP2 entry carries the loop metadata (loop_enumerator/denominator)
    and the RGB color.  Memory cues typically don't have PCP2 entries, but
    the format allows it.
    """
    cue_type_val = 1 if cue_type == "hotcue" else 0
    n = len(cues)
    entries_data = b"".join(
        build_pcp2_entry(
            hot_cue=c["hot_cue"],
            time_ms=c["time_ms"],
            color=tuple(c.get("color", (255, 0, 69))),
            loop_time_ms=c.get("loop_time_ms", -1),
            comment=c.get("comment", ""),
            cue_type=_pcpt_type_for(c),
            loop_num=c.get("loop_num", c.get("loop_enumerator", 0)),
            loop_den=c.get("loop_den", c.get("loop_denominator", 1 if _is_loop(c) else 0)),
        )
        for c in cues
    )
    len_tag = 20 + len(entries_data)

    header = bytearray(20)
    header[0:4] = b"PCO2"
    struct.pack_into(">II", header, 4, 20, len_tag)
    struct.pack_into(">I", header, 12, cue_type_val)  # type = hotcue or memory
    struct.pack_into(">H", header, 16, n)       # count
    struct.pack_into(">H", header, 18, 0)       # unknown

    return bytes(header) + entries_data


# ---------------------------------------------------------------------------
# Cue bank routing: split a flat cues list into memory / hotcue banks
# ---------------------------------------------------------------------------

def split_cue_banks(
    cues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split cues into (memory_bank, hotcue_bank) based on the `type` field.

    A cue dict may specify:
        "type": "memory"  -> goes to the memory cue bank (hot_cue forced to 0)
        "type": "hotcue"  -> goes to the hot cue bank (default)
        (absent)          -> defaults to "hotcue"

    Memory cues ignore the `hot_cue` field (it is always 0 in PCPT).
    """
    memory_bank: list[dict[str, Any]] = []
    hotcue_bank: list[dict[str, Any]] = []
    for c in cues:
        ctype = c.get("type", "hotcue")
        if ctype in ("start", "end"):
            continue
        if ctype == "memory":
            mem = dict(c)
            mem["hot_cue"] = 0  # memory cues always have hot_cue=0
            memory_bank.append(mem)
        else:
            hotcue_bank.append(c)
    return memory_bank, hotcue_bank


def split_db_markers(
    cues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (start_markers, end_markers) destined for exportLibrary.db only."""
    starts = [c for c in cues if c.get("type") == "start"]
    ends = [c for c in cues if c.get("type") == "end"]
    return starts, ends


# ---------------------------------------------------------------------------
# DAT / EXT file mutation
# ---------------------------------------------------------------------------

def write_cues_to_dat(data: bytes, cues: list[dict[str, Any]]) -> bytes:
    """Insert PCOB tags into DAT at end.

    DAT layout convention (from djay / rekordbox exports):
        ... PWV2  PCOB(memory, entries)  PCOB(hotcue, entries)  EOF

    Both banks are written; empty banks get a 0-entry PCOB.  Order matters:
    memory PCOB comes before hotcue PCOB (matches observed djay exports).
    """
    memory_bank, hotcue_bank = split_cue_banks(cues)
    cleaned = strip_cue_tags(data)

    pcob_memory = (
        build_pcob_tag(memory_bank, cue_type="memory")
        if memory_bank
        else build_pcob_empty(cue_type="memory")
    )
    pcob_hotcue = (
        build_pcob_tag(hotcue_bank, cue_type="hotcue")
        if hotcue_bank
        else build_pcob_empty(cue_type="hotcue")
    )

    new_data = cleaned + pcob_memory + pcob_hotcue
    return fix_file_header_length(new_data)


def write_cues_to_ext(data: bytes, cues: list[dict[str, Any]]) -> bytes:
    """Insert PCOB + PCO2 tags into EXT, before PQT2.

    EXT layout convention (from djay / rekordbox exports):
        ... PWV5  PCOB(memory)  PCOB(hotcue)  PCO2(hotcue)  PQT2  EOF

    For each non-empty bank, a PCOB tag is written.  PCO2 (extended with
    colors/comments) is written for the hotcue bank only — memory cues
    traditionally have no color in EXT.  All PCO tags are inserted before
    the trailing PQT2.
    """
    memory_bank, hotcue_bank = split_cue_banks(cues)
    cleaned = strip_cue_tags(data)

    pcob_tags: list[bytes] = []
    if memory_bank:
        pcob_tags.append(build_pcob_tag(memory_bank, cue_type="memory"))
    if hotcue_bank:
        pcob_tags.append(build_pcob_tag(hotcue_bank, cue_type="hotcue"))
        pcob_tags.append(build_pco2_tag(hotcue_bank, cue_type="hotcue"))

    header_len = struct.unpack(">I", cleaned[4:8])[0]
    chunks: list[bytes] = [cleaned[:header_len]]
    inserted = False
    for tag_name, off, len_tag in scan_pmai_tags(cleaned):
        if tag_name == "PQT2" and not inserted:
            chunks.extend(pcob_tags)
            inserted = True
        chunks.append(cleaned[off : off + len_tag])

    if not inserted:
        chunks.extend(pcob_tags)

    new_data = b"".join(chunks)
    return fix_file_header_length(new_data)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_anlz_dir(anlz_dir: Path) -> dict[str, Any]:
    """Read-back DAT, EXT, 2EX using the raw parser."""
    import importlib.util

    dump_path = Path(__file__).resolve().parent / "dump_anlz_cues.py"
    spec = importlib.util.spec_from_file_location("dump_anlz_cues", dump_path)
    dump_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dump_mod)

    result: dict[str, Any] = {"dir": str(anlz_dir)}
    for suffix, fname in [
        ("DAT", "ANLZ0000.DAT"),
        ("EXT", "ANLZ0000.EXT"),
        ("2EX", "ANLZ0000.2EX"),
    ]:
        path = anlz_dir / fname
        if not path.exists():
            continue
        try:
            result[suffix] = dump_mod.raw_dump(path)
        except Exception as exc:
            result[suffix] = {"error": repr(exc)}
    return result


def _analysis_path_for_db(anlz_dir: Path, override: str | None = None) -> str:
    """Map `/Volumes/<VOL>/PIONEER/.../<hash>` dir to DB analysisDataFilePath."""
    if override:
        return override
    parts = anlz_dir.resolve().parts
    try:
        pioneer_idx = parts.index("PIONEER")
    except ValueError as exc:
        raise ValueError(f"ANLZ dir is not inside /PIONEER: {anlz_dir}") from exc
    return "/" + "/".join(parts[pioneer_idx:]) + "/ANLZ0000.DAT"


def write_start_end_to_db(
    db_path: Path,
    anlz_dir: Path,
    cues: list[dict[str, Any]],
    analysis_path_override: str | None = None,
) -> dict[str, Any]:
    """Write start/end load markers to exportLibrary.db as kind=3 rows."""
    starts, ends = split_db_markers(cues)
    if not starts and not ends:
        return {"updated": False, "reason": "no start/end markers"}

    from pyrekordbox import DeviceLibraryPlus
    from pyrekordbox.devicelib_plus import models

    analysis_path = _analysis_path_for_db(anlz_dir, override=analysis_path_override)
    with DeviceLibraryPlus(db_path) as db:
        content = (
            db.query(models.Content)
            .filter_by(analysisDataFilePath=analysis_path)
            .one_or_none()
        )
        if content is None:
            raise SystemExit(f"No content row found for analysisDataFilePath={analysis_path}")

        existing = db.get_cue(content_id=content.content_id).filter_by(kind=3).all()
        removed_count = len(existing)
        for cue in existing:
            db.delete(cue)

        rows_to_add: list[tuple[str, dict[str, Any]]] = []
        if starts:
            rows_to_add.append(("start", starts[0]))
        if ends:
            rows_to_add.append(("end", ends[0]))

        inserted: list[dict[str, Any]] = []
        for marker_type, cue_data in rows_to_add:
            cue = models.Cue(
                content_id=content.content_id,
                kind=3,
                colorTableIndex=0,
                cueComment=marker_type,
                isActiveLoop=0,
                beatLoopNumerator=0,
                beatLoopDenominator=0,
                inUsec=int(cue_data["time_ms"]) * 1000,
                outUsec=0,
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
            db.add(cue)
            inserted.append({"type": marker_type, "time_ms": int(cue_data["time_ms"])})

        content.cueUpdateCount = (content.cueUpdateCount or 0) + len(inserted)
        content.hasModified = 1
        db.flush()
        db.commit()

        return {
            "updated": True,
            "content_id": content.content_id,
            "analysisDataFilePath": analysis_path,
            "removed_existing_kind3": removed_count,
            "inserted": inserted,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", type=Path, help="ANLZ directory (contains ANLZ0000.DAT/.EXT)")
    sub = p.add_subparsers(dest="command", required=True)

    w = sub.add_parser("write", help="Write cue tags into DAT + EXT")
    w.add_argument("--cues", type=str, required=True, help="JSON array of cues")
    w.add_argument("--no-backup", action="store_true", help="Skip backup")

    wdb = sub.add_parser("write-db", help="Write ANLZ cues and exportLibrary.db start/end markers")
    wdb.add_argument("--db", type=Path, required=True, help="Path to exportLibrary.db")
    wdb.add_argument("--cues", type=str, required=True, help="JSON array of cues")
    wdb.add_argument("--no-backup", action="store_true", help="Skip ANLZ backup")
    wdb.add_argument(
        "--analysis-path",
        type=str,
        default=None,
        help="Override analysisDataFilePath lookup in exportLibrary.db",
    )

    d = sub.add_parser("dry-run", help="Show what would be written")
    d.add_argument("--cues", type=str, required=True, help="JSON array of cues")

    sub.add_parser("verify", help="Read back and show current cues")
    return p.parse_args()


def _describe_cue(c: dict[str, Any]) -> str:
    """Human-readable one-liner for a cue dict (used in dry-run/write output)."""
    ctype = c.get("type", "hotcue")
    hot = c.get("hot_cue", 0)
    time_ms = c["time_ms"]
    is_loop = c.get("loop_time_ms", -1) != -1
    color = c.get("color", (255, 0, 69))

    parts: list[str] = []
    if ctype == "memory":
        parts.append("memory")
    elif ctype in ("start", "end"):
        parts.append(ctype)
    else:
        parts.append(f"hotcue={hot}")
    parts.append(f"time={time_ms}ms")
    if is_loop:
        parts.append(f"loop->{c['loop_time_ms']}ms")
        beats = c.get("loop_num", c.get("loop_enumerator", 0))
        if beats:
            parts.append(f"({beats}/{c.get('loop_den', 1)})")
    if ctype == "hotcue":
        parts.append(f"rgb={tuple(color)}")
    comment = c.get("comment", "")
    if comment:
        parts.append(f"comment={comment!r}")
    return " ".join(parts)


def main() -> None:
    args = parse_args()
    target: Path = args.path.resolve()

    if not target.is_dir():
        sys.exit(f"Not a directory: {target}")

    ext_path = target / "ANLZ0000.EXT"
    dat_path = target / "ANLZ0000.DAT"

    if args.command in ("write", "dry-run", "write-db"):
        cues: list[dict[str, Any]] = json.loads(args.cues)
        anlz_cues = [c for c in cues if c.get("type", "hotcue") not in ("start", "end")]
        start_markers, end_markers = split_db_markers(cues)
        memory_bank, hotcue_bank = split_cue_banks(cues)
        print(f"Cues to write: {len(cues)} "
              f"(memory={len(memory_bank)}, hotcue={len(hotcue_bank)}, "
              f"start={len(start_markers)}, end={len(end_markers)})")
        for c in cues:
            print(f"  {_describe_cue(c)}")

        if args.command == "dry-run":
            for path, writer in [(dat_path, write_cues_to_dat), (ext_path, write_cues_to_ext)]:
                if not path.exists():
                    print(f"\n{path.name}: missing")
                    continue
                orig = path.read_bytes()
                new = writer(orig, anlz_cues)
                print(f"\n{path.name}: {len(orig)} → {len(new)} bytes ({len(new) - len(orig):+d})")
            return

        # Actual write
        do_backup = not args.no_backup
        for path, writer in [(dat_path, write_cues_to_dat), (ext_path, write_cues_to_ext)]:
            if not path.exists():
                print(f"\n{path.name}: missing, skipping")
                continue
            if do_backup:
                bak = path.parent / (path.name + ".bak")
                bak.write_bytes(path.read_bytes())
                print(f"Backup: {bak}")

            orig = path.read_bytes()
            new = writer(orig, anlz_cues)
            path.write_bytes(new)
            print(f"{path.name} written: {len(new)} bytes")

        if args.command == "write-db":
            db_result = write_start_end_to_db(
                args.db.resolve(),
                target,
                cues,
                analysis_path_override=args.analysis_path,
            )
            print("\nDB markers:")
            print(json.dumps(db_result, indent=2, default=str))

        print("\nDone. Eject and re-insert USB, then check rekordbox.")

    elif args.command == "verify":
        result = verify_anlz_dir(target)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
