"""Parity test — ``app/shared/ui_colors.py`` ↔ ``panel/lib/constants.ts``.

The Prefab UI tools and the Next.js Panel share the same DJ vocabulary
(15 subgenres). To keep both in sync, we assert that the key sets in
``SUBGENRE_COLORS`` / ``SUBGENRE_LABELS`` on the Python side match the
TypeScript source of truth exactly. Colors / label text may drift, but
adding or removing a subgenre on either side must be an intentional
two-file change.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.shared.ui_colors import SUBGENRE_COLORS, SUBGENRE_LABELS

PANEL_CONSTANTS = Path(__file__).resolve().parent.parent.parent / "panel" / "lib" / "constants.ts"


def _parse_keys(ts_source: str, object_name: str) -> set[str]:
    """Extract the keys of a `Record<string, string>` object literal."""
    pattern = re.compile(
        rf"export const {re.escape(object_name)}:\s*Record<string,\s*string>\s*=\s*\{{([^}}]*)\}}",
        re.DOTALL,
    )
    match = pattern.search(ts_source)
    assert match is not None, f"could not locate {object_name} in {PANEL_CONSTANTS}"
    body = match.group(1)
    # Keys are bare identifiers followed by a colon.
    return set(re.findall(r"([a-zA-Z_][a-zA-Z_0-9]*)\s*:\s*'", body))


def test_subgenre_colors_keys_match_panel() -> None:
    source = PANEL_CONSTANTS.read_text()
    ts_keys = _parse_keys(source, "SUBGENRE_COLORS")
    py_keys = set(SUBGENRE_COLORS.keys())
    assert ts_keys == py_keys, (
        f"SUBGENRE_COLORS keys drifted: ts-only={ts_keys - py_keys}  py-only={py_keys - ts_keys}"
    )


def test_subgenre_labels_keys_match_panel() -> None:
    source = PANEL_CONSTANTS.read_text()
    ts_keys = _parse_keys(source, "SUBGENRE_LABELS")
    py_keys = set(SUBGENRE_LABELS.keys())
    assert ts_keys == py_keys, (
        f"SUBGENRE_LABELS keys drifted: ts-only={ts_keys - py_keys}  py-only={py_keys - ts_keys}"
    )


def test_all_15_subgenres_present() -> None:
    # Ordering from REQUIREMENTS.md §3.3 — 15 techno subgenres.
    expected = {
        "ambient_dub",
        "dub_techno",
        "minimal",
        "detroit",
        "melodic_deep",
        "progressive",
        "hypnotic",
        "driving",
        "tribal",
        "breakbeat",
        "peak_time",
        "acid",
        "raw",
        "industrial",
        "hard_techno",
    }
    assert set(SUBGENRE_COLORS.keys()) == expected
    assert set(SUBGENRE_LABELS.keys()) == expected


def test_camelot_wheel_has_24_slots() -> None:
    from app.shared.ui_colors import CAMELOT_WHEEL_COLORS

    assert len(CAMELOT_WHEEL_COLORS) == 24
    # 12 positions x 2 modes (A/B) covers all codes 0..23
    labels = set(CAMELOT_WHEEL_COLORS.keys())
    for n in range(1, 13):
        assert f"{n}A" in labels
        assert f"{n}B" in labels
